# -*- coding: utf-8 -*-
"""The engine: declarations plus emitters plus the filesystem, and the only thing that writes.

    py scaffold.py <vault-root> [--apply|--rollback] [--archetype X] [--only id,...] [--force id]

`--plan` is the default and writes nothing.

Order matters and is not incidental. The generated regions of CLAUDE.md are filled LAST,
because `structure` reads the folders that step 2 created, `card-index` reads the classes,
and `skills-index` would read skills that do not exist yet. Filling them earlier produces a
table that is wrong the moment the next step runs.

The five-state classifier is the whole re-run story:

    ABSENT  write   CLEAN  no-op   STALE  regenerate
    DIRTY   skip and report, except on a seeded file where an edit is the point
    FOREIGN skip and report; nothing here has ever recorded writing it

FOREIGN means "this package holds no stamp for this file", which is not the same claim as
"a person wrote it". Two artefacts cannot hold a stamp at all - `registry.base` is bare YAML
and `START-HERE.md` carries no frontmatter - so for years both read FOREIGN on every run of
every vault, including one written seconds earlier, and the branch wrote over them anyway.
Their stamps now live in `_system/os/stamps.json`, and a file with no record there is
compared against what would be written before anything is concluded: an exact match is proof
it is ours and the record is simply written down, and a difference is proof of nothing and is
therefore skipped. `--force <id>` is the way back for a file that really should be taken.
"""
import io
import json
import os
import time
import tomllib

from . import VERSION, decl, fm, fsplan, regions, stamp
from .emit import (load_labels, agent, bases, bond, cardskill, claudemd, starthere,
                   vocabulary, workflow)

GENERATED_BY = 'solai@%s' % VERSION
OS_DIR = '_system/os'
BUILD_LEDGER = OS_DIR + '/build.md'
ANSWERS = OS_DIR + '/answers.toml'
MANIFEST = OS_DIR + '/apply-manifest.json'
# The stamps of artefacts whose own format cannot carry one. Engine state, like the manifest
# beside it, and not the same file: that one holds the PRE-image for a rollback, is rewritten
# on every apply, and carries no row at all for a file that did not change - which is the one
# case a provenance record exists for.
STAMPS = OS_DIR + '/stamps.json'
BACKUP = OS_DIR + '/_backup'

# Caps are a refusal, not a warning. An empty folder cannot be initialised above `light`:
# a schema over nothing is a schema that will be rewritten before it is ever read.
TIER_CAPS = {'minimal': (2, 0), 'light': (4, 1), 'standard': (9, 3), 'governed': (16, 5)}
TIER_REQUIRES = {'standard': 20, 'governed': 150}


class Result(object):
    def __init__(self):
        self.plan = None
        self.errors = []
        self.notes = []
        self.deferred = []
        # What every generated region WOULD contain, keyed by artefact path then region id.
        # Recorded even when the plan is a NOOP, because that is exactly when someone asks
        # `--diff` what a hand-edited block would say if it were regenerated.
        self.regions = {}


# --------------------------------------------------------------------------- helpers

def _today():
    return time.strftime('%Y-%m-%d')


def count_content(root):
    """Content files: everything that is not engine state, config or app data."""
    n = 0
    skip = {'.obsidian', '.trash', '.git', 'node_modules', '.claude', '__pycache__'}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        rel = os.path.relpath(dirpath, root).replace(os.sep, '/')
        if rel.startswith('_system'):
            continue
        n += len([f for f in filenames if f.endswith('.md') and f != 'CLAUDE.md'])
    return n


def write_answers(path, answers):
    """Minimal TOML writer. tomllib is read-only by design, and the answers file is flat."""
    lines = ['# Setup answers. Re-running the engine reuses these unless --reanswer is given.']
    for k in sorted(answers):
        v = answers[k]
        if isinstance(v, bool):
            lines.append('%s = %s' % (k, 'true' if v else 'false'))
        elif isinstance(v, int):
            lines.append('%s = %d' % (k, v))
        elif isinstance(v, (list, tuple)):
            lines.append('%s = [%s]' % (k, ', '.join('"%s"' % str(x).replace('"', "'") for x in v)))
        elif v is None:
            continue
        else:
            lines.append('%s = "%s"' % (k, str(v).replace('"', "'")))
    with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')


def read_answers(path):
    import tomllib
    if not os.path.exists(fsplan.w(path)):
        return {}
    with open(fsplan.w(path), 'rb') as fh:
        return tomllib.load(fh)


# --------------------------------------------------------------------------- classify

def classify_file(existing, expected_src, mode, volatile=None):
    if existing is None:
        return 'ABSENT'
    if mode == 'seeded':
        return 'SEEDED-PRESENT'
    v = stamp.verdict(existing, expected_src, volatile)
    return {stamp.UNSTAMPED: 'FOREIGN'}.get(v, v)


def classify_recorded(existing, record, expected_src, volatile=None):
    """The same five states for an artefact whose format carries no stamp.

    `UNSTAMPED` becomes `FOREIGN` here too, but it means something weaker: no record, so this
    package has never written down having written this file. That is the state of every vault
    built before the record existed, and it is why the caller compares the file against what it
    would emit before it concludes anything. A byte-for-byte match is proof of authorship; a
    difference is not proof of anything, which is exactly why it must not be overwritten.
    """
    if existing is None:
        return 'ABSENT'
    v = stamp.verdict_recorded(existing, record, expected_src, volatile)
    return {stamp.UNSTAMPED: 'FOREIGN'}.get(v, v)


class Stamps(object):
    """The stamps of artefacts whose format carries none: read at plan time, written at the end.

    Two dictionaries rather than one. `existing` is what the vault came with and is never
    mutated, because the classifier must go on answering from the same record for the whole
    plan. `next` is what the vault will hold afterwards, and an artefact that is SKIPPED leaves
    its entry exactly as it found it: a file this package refused to write is a file it must not
    claim to have written.
    """

    def __init__(self, existing=None):
        self.existing = dict(existing or {})
        self.next = dict(self.existing)

    def get(self, path):
        return self.existing.get(path)

    def put(self, path, record):
        self.next[path] = record

    @property
    def changed(self):
        return self.next != self.existing

    def text(self, package_version):
        """Sorted, indented, and with no timestamp in it.

        A file that recorded when it was written would differ from itself on every run, so the
        plan would carry a WRITE row forever and no second run could be a NOOP. The version is
        in here because it is already inside every `source-sha`, so a release moves this file
        for the same reason it moves every stamped artefact.
        """
        return json.dumps({'package_version': package_version,
                           'artefacts': self.next},
                          ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def read_stamps(root):
    """-> {vault-relative path: record}. A missing or unreadable file is an empty record set."""
    text = fsplan.read(os.path.join(root, STAMPS.replace('/', os.sep)))
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    got = data.get('artefacts')
    return got if isinstance(got, dict) else {}


RECONCILED = 'RECONCILED'
ADOPTED = 'ADOPTED'


def read_adopted(root):
    """Hand edits somebody has taken responsibility for -> {(artefact, region): record}.

    An adopted region is still skipped and still never overwritten. What changes is that the
    divergence has a name, a date and a change record instead of being an anonymous dirty
    block nobody can account for. Edit it again and its sha stops matching, and it reads
    HAND-EDITED once more.
    """
    p = os.path.join(root, '_system', 'os', 'adopted.toml')
    out = {}
    if not os.path.exists(p):
        return out
    try:
        with open(p, 'rb') as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return out
    for row in data.get('adopted', []):
        out[(row.get('artefact'), row.get('region'))] = row
    return out


def merge_regions(existing, region_text, expected_src, order, force=(), adopted=None):
    """-> (new_text, per_region_verdict). A dirty region costs one region, not the file."""
    text, verdicts = existing, {}
    for rid in order:
        if rid not in region_text:
            continue
        found = regions.find_all(text).get(rid)
        if found is None:
            verdicts[rid] = 'ABSENT'
            text = regions.insert(text, rid, region_text[rid], expected_src, order=order)
            continue
        v = found.verdict(expected_src)
        if v == stamp.HAND_EDITED and rid not in force:
            # RECONCILED. The body no longer matches its stamp, AND it is byte-identical to
            # what the declaration now produces: somebody edited the block to say what the
            # declaration has since caught up with. Re-stamp and report it. Nothing is
            # discarded and no visible byte changes.
            #
            # This is NOT the act `lib/stamp.py` forbids. That is rewriting a hash to silence
            # a mismatch with UNKNOWN content. This corrects a hash over content the
            # declaration provably generates. Without the rule a block stays permanently
            # dirty even once its content has become correct, which is a wart with no upside.
            if found.content.strip() == region_text[rid].strip():
                verdicts[rid] = RECONCILED
                text = regions.replace(text, rid, region_text[rid], expected_src)
                continue
            row = (adopted or {}).get(rid)
            if row and row.get('body-sha') == stamp.body_sha(found.content):
                verdicts[rid] = '%s %s' % (ADOPTED, row.get('because') or 'no record named')
                continue
            verdicts[rid] = stamp.HAND_EDITED
            continue
        if v == stamp.CLEAN and found.content.strip() == region_text[rid].strip():
            verdicts[rid] = stamp.CLEAN
            continue
        verdicts[rid] = v if v != stamp.CLEAN else stamp.STALE
        text = regions.replace(text, rid, region_text[rid], expected_src)
    return text, verdicts


# --------------------------------------------------------------------------- the build

def collect_materials(paths, root):
    """-> (files, errors), where a file is the pair (source, name it takes inside the vault).
    A path is a file or a folder; a folder is walked and its tree is mirrored, so two documents
    that share a basename in different subfolders both arrive and neither overwrites the other.
    A name is only refused when two of the given paths hold it at the same relative place and
    the folders they came from cannot tell them apart either. A path inside the vault itself is
    refused, because copying a vault into its own inbox is never what was meant."""
    picked, errors = [], []
    for given in paths:
        p = os.path.abspath(given)
        if not fsplan.exists(p):
            errors.append('no such path: %s' % given)
            continue
        if p.startswith(os.path.abspath(root) + os.sep):
            errors.append('%s is inside the vault itself' % given)
            continue
        if os.path.isdir(fsplan.w(p)):
            base_dir = fsplan.w(p)
            for base, dirs, names in os.walk(base_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for n in sorted(names):
                    if n.startswith('.'):
                        continue
                    f = os.path.join(base, n)
                    picked.append((f, _material_rel(f, base_dir), os.path.basename(p)))
        else:
            picked.append((p, os.path.basename(p), os.path.basename(os.path.dirname(p))))

    # One relative name may be claimed by more than one of the given paths. Prefixing each with
    # the folder it came from separates them; only when that fails too is anything refused, and
    # then the message says what to do about it.
    by_rel = {}
    for source, rel, origin in picked:
        by_rel.setdefault(rel, []).append((source, origin))
    files = []
    for rel, group in sorted(by_rel.items()):
        if len(set(source for source, _ in group)) == 1:
            files.append((group[0][0], rel))
            continue
        taken = {}
        for source, origin in group:
            name = (origin + '/' + rel) if origin else rel
            if taken.get(name, source) != source:
                errors.append('two files are called %s: %s and %s. Hand in the one folder that '
                              'holds both, instead of the two paths, or rename one of them.'
                              % (rel, taken[name], source))
                continue
            taken[name] = source
        files += [(source, name) for name, source in taken.items()]
    return sorted(set(files)), errors


def _material_rel(path, base_dir):
    """The name a walked file takes inside the inbox: its path under the folder that was
    handed in, with forward slashes, which is what `fsplan.Plan.path` expects."""
    return os.path.relpath(path, base_dir).replace(os.sep, '/')


def build_plan(root, pkg_root, answers, arch, result, only=None, force=(), materials=()):
    L = load_labels(pkg_root, answers.get('output_language', 'en'))
    tier = answers.get('governance_tier', arch.default_tier)
    partition = answers.get('partition') or []
    classes = arch.classes
    plan = fsplan.Plan(root, VERSION)

    def wanted(aid):
        return (not only) or aid in only

    manifest_path = os.path.join(arch.root, 'manifest.toml')
    manifest_body = arch.manifest_text
    if manifest_body is None and os.path.exists(manifest_path):
        manifest_body = io.open(manifest_path, encoding='utf-8').read()

    src_inputs = [(os.path.basename(c.path), stamp.file_sha(c.path)) for c in classes]
    # An agent declaration is a source like a class declaration: editing one must make the
    # projections read STALE, and leaving it out of the hash is how a stamp starts lying.
    src_inputs += [('agent:' + os.path.basename(a.path), stamp.file_sha(a.path))
                   for a in arch.agents]
    src_inputs += [('workflow:' + os.path.basename(w.path), stamp.file_sha(w.path))
                   for w in arch.workflows]
    # The manifest hashed here is the one this plan WRITES, which under a merge is not the
    # file sitting at `arch.root`: the class list has been widened to name what the vault
    # kept. Hashing the package copy instead would stamp every region against a manifest the
    # vault does not hold, and the next plain run would read its own manifest as a changed
    # source and rewrite all of them.
    src_inputs.append(('manifest', stamp.sha(manifest_body) if manifest_body is not None
                       else None))
    src_inputs.append(('lang', answers.get('output_language', 'en')))
    src_inputs.append(('tier', tier))

    def src_for(emitter):
        return stamp.source_sha(VERSION, emitter, src_inputs)

    # Hand edits somebody has signed for. Keyed by artefact path, then region id, so a
    # merge only ever consults the rows written about the file it is merging.
    # The stamps of the artefacts whose format carries none, read once. Every classification
    # in this plan answers from the same record, and what the vault will hold afterwards is
    # accumulated separately and written at the end.
    stamps = Stamps(read_stamps(root))

    adopted_rows = read_adopted(root)
    adopted = {}
    for (art_path, rid), row in adopted_rows.items():
        adopted.setdefault(art_path, {})[rid] = row

    # 1 folders --------------------------------------------------------------
    for f in arch.folders:
        p = f.get('path')
        if p and not fsplan.exists(plan.path(p)):
            plan.mkdir(p)
    for c in classes:
        if not fsplan.exists(plan.path(c.folder)):
            plan.mkdir(c.folder)

    # 2 copied runtime and shared --------------------------------------------
    for art in arch.artefacts:
        if art.get('mode') != 'copied' or not wanted(art['id']):
            continue
        for name in art.get('files', []):
            source = os.path.join(pkg_root, art['from'].rstrip('/'), name)
            target = art['path'].rstrip('/') + '/' + name
            if not os.path.exists(fsplan.w(source)):
                result.errors.append('%s: no such file to copy: %s' % (art['id'], source))
                continue
            cur = fsplan.read(plan.path(target))
            if cur is not None and stamp.file_sha(source) == stamp.sha(cur):
                plan.noop(target, art['id'])
            elif cur is not None:
                plan.skip(target, art['id'], 'LOCAL', 'differs from the shipped copy')
            else:
                plan.copy(target, art['id'], source)

    # 2b materials handed in at setup ----------------------------------------
    # Copied, never opened. Deciding that this document constitutes the role and that one is
    # background is a judgement, and judgement belongs to a session with an agent in it, not
    # to a plan that has to stay a projection of the declarations (D12). They land in the
    # folder the archetype declares for unprocessed capture, and the first session files them.
    if materials:
        dest = (arch.materials or '').rstrip('/')
        if not any(dest == (f.get('path') or '').rstrip('/') for f in arch.folders):
            result.errors.append('materials: this archetype declares no folder %r to drop '
                                 'them in.' % dest)
        else:
            found, errs = collect_materials(materials, root)
            for e in errs:
                result.errors.append('materials: %s' % e)
            for source, rel in found:
                target = dest + '/' + rel
                here = plan.path(target)
                if fsplan.exists(here):
                    if fsplan.bytes_sha(source) == fsplan.bytes_sha(here):
                        plan.noop(target, 'materials')
                    else:
                        plan.skip(target, 'materials', 'LOCAL',
                                  'a different file of this name is already there')
                else:
                    plan.copy(target, 'materials', source)

    # 2c the manifest compiled in, so the vault holds the whole declaration --------
    # Classes, agents and workflows were already copied here; the manifest was the one file
    # left behind, and it holds the four things the emitters cannot get from a class: the
    # folders, the loop, the date format and the artefact list. Without it a vault could be
    # VALIDATED against its own declarations and never REGENERATED from them, which is how
    # one vault ended up with a hand-maintained section listing the generated blocks that
    # had gone wrong and could not be fixed from inside it.
    #
    # Hardcoded here rather than declared as an artefact, because the three declaration
    # copies above have no artefact entry either and the precedent should not fork.
    #
    # `arch.manifest_text` is set only by a merge load, where the body written is the package
    # manifest with its class list widened to name the declarations the vault kept. Copying
    # the package file there instead would leave a compiled manifest that does not list what
    # is in the directory beside it, and the next run would read those classes as strays and
    # reorder every generated index around them.
    if manifest_body is not None:
        target = OS_DIR + '/manifest.toml'
        body = manifest_body
        cur = fsplan.read(plan.path(target))
        if cur == body:
            plan.noop(target, 'declarations')
        else:
            plan.write(target, 'declarations', body)

    # 3 declarations compiled into the vault ---------------------------------
    for c in classes:
        target = OS_DIR + '/classes/' + os.path.basename(c.path)
        body = io.open(c.path, encoding='utf-8').read()
        cur = fsplan.read(plan.path(target))
        if cur == body:
            plan.noop(target, 'declarations')
        else:
            plan.write(target, 'declarations', body)

    # 3b agent declarations compiled in, for the same reason as the classes: a place reads
    # its own compiled declarations and never the package it was built from.
    for a in arch.agents:
        target = OS_DIR + '/agents/' + os.path.basename(a.path)
        body = io.open(a.path, encoding='utf-8').read()
        cur = fsplan.read(plan.path(target))
        if cur == body:
            plan.noop(target, 'declarations')
        else:
            plan.write(target, 'declarations', body)

    # 3c workflow declarations compiled in, beside the agents and the classes.
    for w in arch.workflows:
        target = OS_DIR + '/workflows/' + os.path.basename(w.path)
        body = io.open(w.path, encoding='utf-8').read()
        cur = fsplan.read(plan.path(target))
        if cur == body:
            plan.noop(target, 'declarations')
        else:
            plan.write(target, 'declarations', body)

    # 4 data dictionary -------------------------------------------------------
    art = arch.artefact('data-dictionary')
    if art and wanted('data-dictionary'):
        from .emit import classes as EC
        s = src_for('classes')
        text = EC.render_all(classes, L, partition, arch.lookups)
        _merged(plan, art, s, text, art.get('regions', []), force, result,
                lambda: EC.skeleton(L, text, tuple(art.get('regions', [])), s),
                fmeta={'date': _today(), 'type': 'reference',
                       'title': '"%s (GENERATED)"' % L('dd.title'), 'tags': []},
                adopted=adopted.get(art['path'], {}))

    # 5 vocabulary ------------------------------------------------------------
    art = arch.artefact('vocabulary')
    if art and wanted('vocabulary'):
        s = src_for('vocabulary')
        text = {'keys': vocabulary.keys_region(classes, arch, L)}
        _merged(plan, art, s, text, ['keys'], force, result,
                lambda: vocabulary.skeleton(L, text['keys'], s),
                fmeta={'date': _today(), 'type': 'reference', 'title': '"Vocabulary"',
                       'tags': []},
                adopted=adopted.get(art['path'], {}))

    # 6 card skills -----------------------------------------------------------
    art = arch.artefact('card-skills')
    if art and wanted('card-skills'):
        shared = ['.claude/skills/_shared/%s.md' % s for s in ()]
        for c in classes:
            s = src_for('cardskill:' + c.name)
            target = art['path'].replace('{skill}', c.skill)
            shared = ['.claude/skills/_shared/%s.md' % x for x in c.skill_shared]
            rt = cardskill.render_regions(c, L, answers.get('name', ''), tier,
                                          answers.get('output_language', 'en'), partition)
            cur = fsplan.read(plan.path(target))
            if cur is None:
                body = cardskill.skeleton(c, L, rt, shared, src=s)
                ok, n, advice = cardskill.check_size(body, c)
                if not ok:
                    result.errors.append(advice)
                    continue
                plan.write(target, 'skill:' + c.skill, body, src=s)
            else:
                result.regions.setdefault(target, {}).update(rt)
                new, verdicts = merge_regions(cur, rt, s, list(cardskill.REGIONS), force, adopted.get(target, {}))
                _record_merge(plan, target, 'skill:' + c.skill, cur, new, verdicts)

    # 6b agents ---------------------------------------------------------------
    # The seventh emitter, and this is the whole of its wiring: same four write modes, same
    # stamps, same region merge, same plan table. Nothing in the engine core changed to carry
    # it, which was the test the design existed to pass.
    art = arch.artefact('agents')
    if art and wanted('agents'):
        for a in arch.agents:
            s = src_for('agent:' + a.name)
            target = art['path'].replace('{agent}', a.name)
            rt = agent.render_regions(a, L, answers.get('name', ''), tier)
            cur = fsplan.read(plan.path(target))
            if cur is None:
                body = agent.skeleton(a, L, rt, src=s)
                ok, n, advice = agent.check_size(body, a)
                if not ok:
                    result.errors.append(advice)
                    continue
                plan.write(target, 'agent:' + a.name, body, src=s)
            else:
                result.regions.setdefault(target, {}).update(rt)
                new, verdicts = merge_regions(cur, rt, s, list(agent.REGIONS), force, adopted.get(target, {}))
                _record_merge(plan, target, 'agent:' + a.name, cur, new, verdicts)

    # 6c workflows -------------------------------------------------------------
    # The eighth emitter, wired exactly like the seventh. A `.js` carries its stamp in a line
    # comment rather than in frontmatter, which the region machinery already supports: the
    # marker is an HTML comment behind a `// `, and both are legal where they sit.
    art = arch.artefact('workflows')
    if art and wanted('workflows'):
        by_name = {a.name: a for a in arch.agents}
        for w in arch.workflows:
            s = src_for('workflow:' + w.name)
            target = art['path'].replace('{workflow}', w.name)
            rt = workflow.render_regions(w, by_name)
            cur = fsplan.read(plan.path(target))
            if cur is None:
                body = workflow.skeleton(w, by_name, rt, src=s)
                ok, n, advice = workflow.check_size(body, w)
                if not ok:
                    result.errors.append(advice)
                    continue
                bad = workflow.forbidden_in(body)
                if bad:
                    result.errors.append(
                        'workflow %s: the projection contains %s, which breaks resume: the same '
                        'script would make a different call sequence on the second run and the '
                        'cached prefix would stop matching.' % (w.name, ', '.join(bad)))
                    continue
                plan.write(target, 'workflow:' + w.name, body, src=s)
            else:
                result.regions.setdefault(target, {}).update(rt)
                new, verdicts = merge_regions(cur, rt, s, list(workflow.REGIONS), force, adopted.get(target, {}))
                _record_merge(plan, target, 'workflow:' + w.name, cur, new, verdicts)

    # 6d skills projecting a class nobody declares any more --------------------
    # Reported, never deleted. D7 requires a retirement to name the fate of every affected
    # artefact from a closed set, and the engine cannot know which fate the cards deserve.
    # Before this, retiring a class left a live skill writing into a folder that no longer
    # existed and nothing said so: one vault ran four days that way, and its own
    # hand-written "known drift" section - the place such a thing was supposed to be
    # recorded - sat empty. This class of drift is computed, not remembered.
    if arch.artefact('card-skills') and wanted('card-skills'):
        skills_dir = os.path.join(root, '.claude', 'skills')
        live = {c.skill for c in classes} | {c.skill for c in arch.lookups}
        for name in sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else ():
            if name.startswith('_') or name in live:
                continue
            if not os.path.exists(os.path.join(skills_dir, name, 'SKILL.md')):
                continue
            result.deferred.append(
                '.claude/skills/%s/SKILL.md projects a class no longer declared. Retire it '
                'with a change record naming the fate of its cards: leave, migrate, '
                'regenerate, orphan.' % name)

    # 7 base ------------------------------------------------------------------
    art = arch.artefact('registry-base')
    if art and wanted('registry-base') and classes:
        s = src_for('bases')
        body = bases.render(classes, arch.lookups)
        _generated(plan, art['path'], 'registry-base', body, s, force,
                   volatile=bases.VOLATILE, fmeta=None, stamps=stamps)

    # 7b start here -----------------------------------------------------------
    # Written before the seeded files and before CLAUDE.md, because it is the one a person
    # opens first and the order of the plan table is the order a reader will scan.
    art = arch.artefact('start-here')
    if art and wanted('start-here'):
        s = src_for('starthere')
        inbox = arch.materials if any((f.get('path') or '') == arch.materials
                                      for f in arch.folders) else ''
        body = starthere.render(L, arch, classes,
                                dict(answers, package_version=VERSION), inbox)
        _generated(plan, art['path'], 'start-here', body, s, force, fmeta=None,
                   stamps=stamps)

    # 8 seeded files -----------------------------------------------------------
    for art in arch.artefacts:
        if art.get('mode') != 'seeded' or not wanted(art['id']):
            continue
        frag = os.path.join(pkg_root, 'common', 'fragments',
                            art['fragment'].replace('/', os.sep))
        if not os.path.exists(fsplan.w(frag)):
            result.deferred.append('%s: no fragment at %s' % (art['id'], art['fragment']))
            continue
        if fsplan.exists(plan.path(art['path'])):
            plan.noop(art['path'], art['id'], 'SEEDED', 'yours now, never rewritten')
            continue
        body = claudemd.fragment(pkg_root, art['fragment'], answers)
        plan.write(art['path'], art['id'], body + '\n')

    # 9 CLAUDE.md, last of the content steps ----------------------------------
    art = arch.artefact('claude-md')
    if art and wanted('claude-md'):
        s = src_for('claudemd')
        gen = claudemd.render_generated(L, arch, classes, answers)
        order = art.get('regions', [])
        cur = fsplan.read(plan.path('CLAUDE.md'))
        result.regions.setdefault('CLAUDE.md', {}).update(gen)
        if cur is None:
            body = claudemd.skeleton(pkg_root, L, arch, classes, answers, order, gen, s)
            plan.write('CLAUDE.md', 'claude-md', body, src=s)
        else:
            result.regions.setdefault('CLAUDE.md', {}).update(gen)
            new, verdicts = merge_regions(cur, gen, s, order, force,
                                          adopted.get(art['path'], {}))
            _record_merge(plan, 'CLAUDE.md', 'claude-md', cur, new, verdicts)

    # 10 the bond, written last: it reports counts of everything above --------
    art = arch.artefact('bond')
    if art and wanted('bond'):
        s = src_for('bond')
        # Counts are frozen at first build and never refreshed. They record what the
        # bootstrap ratio WAS, which is a historical fact and the thing worth keeping. A
        # file that recounts itself on every run is stale the moment it is written and
        # rewrites itself forever, which would break idempotence on the one file whose job
        # is to make re-running safe. Live counts belong in `solai` status, computed there.
        if 'built-content' in answers:
            counts = {'content': int(answers['built-content']),
                      'system': int(answers['built-system']),
                      'skills': int(answers['built-skills'])}
        else:
            counts = {
                'content': count_content(root),
                'system': len([a for a in plan.actions
                               if a.kind in (fsplan.WRITE, fsplan.COPY)
                               and (a.rel.startswith('_system') or a.rel.startswith('.claude')
                                    or a.rel == 'CLAUDE.md')]),
                'skills': len(classes) + len(arch.agents) + len(arch.workflows),
            }
            answers['built-content'] = counts['content']
            answers['built-system'] = counts['system']
            answers['built-skills'] = counts['skills']
        body = bond.render(answers, arch, classes, tier, counts, VERSION)
        fmt = bond.frontmatter(answers, arch, tier, VERSION)
        _generated(plan, art['path'], 'bond', body, s, force, fmeta_text=fmt)

    # 11 the stamps of what cannot carry one, written last because it records the rest ----
    # Planned like any other write, so it is backed up, named in the apply manifest and undone
    # by `--rollback` with everything else. Nothing at all is planned for a vault with no
    # unstampable artefact in it: an empty record file is a file that explains nothing.
    if stamps.next:
        target, body = STAMPS, stamps.text(VERSION)
        if fsplan.read(plan.path(target)) == body:
            plan.noop(target, 'stamps')
        else:
            plan.write(target, 'stamps', body)

    return plan, L, tier


TAKE_IT = ('; take it with `--force %s`, which overwrites what is there. '
           'There is no undoing that except `--rollback`')


def _generated(plan, path, aid, body, src, force, volatile=None, fmeta=None, fmeta_text=None,
               stamps=None):
    cur = fsplan.read(plan.path(path))
    if fmeta_text is not None:
        new = stamp.stamped_text(fmeta_text, body, src, GENERATED_BY, volatile)
    elif fmeta is not None:
        fmt = '\n'.join('%s: %s' % (k, v if not isinstance(v, list) else '[]')
                        for k, v in fmeta.items())
        new = stamp.stamped_text(fmt, body, src, GENERATED_BY, volatile)
    else:
        return _unstamped(plan, path, aid, stamp.normalise(body), cur, src, force,
                          volatile, stamps)
    state = classify_file(cur, src, 'generated', volatile)
    if state == 'ABSENT':
        plan.write(path, aid, new, src=src)
    elif state == stamp.HAND_EDITED and aid not in force:
        plan.skip(path, aid, stamp.HAND_EDITED, 'hand-edited; not overwritten')
    elif cur == new:
        plan.noop(path, aid)
    else:
        plan.write(path, aid, new, src=src,
                   verdict=state if state != stamp.CLEAN else 'CONTENT-CHANGED')


def _unstamped(plan, path, aid, new, cur, src, force, volatile, stamps):
    """The same five states for a file that cannot carry a stamp, read from the sidecar.

    The one state with no counterpart above is `FOREIGN` with no record, and it splits in two
    by evidence rather than by assumption. If the file hashes to what would be written it is
    this engine's output whoever put it there, so the record is written down and nothing else
    happens; that is adoption, and it needs no flag because the comparison has already proved
    what a flag would have asserted. If it does not, the file is somebody's, and it is skipped.

    Comparing hashes rather than bytes is what finally reaches `strip_volatile` on the one
    artefact it was written for. The column widths Obsidian writes into a `.base` the moment
    anybody opens it stop counting as a difference, so an apply no longer discards them.
    """
    record = stamps.get(path) if stamps is not None else None
    state = classify_recorded(cur, record, src, volatile)
    mine = stamp.record_for(new, src, GENERATED_BY, volatile)

    def keep():
        if stamps is not None and record:
            stamps.put(path, record)

    def write(verdict=None):
        if stamps is not None:
            stamps.put(path, mine)
        plan.write(path, aid, new, src=src, verdict=verdict)

    if state == 'ABSENT':
        return write()
    if state == stamp.CLEAN:
        # CLEAN without being byte-identical means the volatile keys moved and nothing else.
        keep()
        return plan.noop(path, aid)
    if state == 'FOREIGN' and stamp.body_sha(cur, volatile) == mine[stamp.KEY_BODY]:
        # Ours, demonstrably. Writing the record down is the whole of the adoption.
        if stamps is not None:
            stamps.put(path, mine)
        return plan.noop(path, aid, verdict='FOREIGN',
                         reason='not recorded, and identical: adopted')
    if state == 'FOREIGN' and aid not in force:
        keep()
        return plan.skip(path, aid, 'FOREIGN',
                         'no record of this package writing it, and it differs from what '
                         'would be written' + TAKE_IT % aid)
    if state == stamp.HAND_EDITED and aid not in force:
        keep()
        return plan.skip(path, aid, stamp.HAND_EDITED,
                         'hand-edited; not overwritten' + TAKE_IT % aid)
    return write(state)


def _merged(plan, art, src, region_text, order, force, result, first_write,
            fmeta=None, adopted=None):
    path = art['path']
    result.regions.setdefault(path, {}).update(region_text)
    cur = fsplan.read(plan.path(path))
    if cur is None:
        body = first_write()
        if fmeta:
            fmt = '\n'.join('%s: %s' % (k, v if not isinstance(v, list) else '[]')
                            for k, v in fmeta.items())
            body = fm.join(fmt, stamp.normalise(body))
        plan.write(path, art['id'], body, src=src)
        return
    new, verdicts = merge_regions(cur, region_text, src, list(order), force, adopted)
    _record_merge(plan, path, art['id'], cur, new, verdicts)


def _record_merge(plan, path, aid, cur, new, verdicts):
    dirty = [r for r, v in verdicts.items() if v == stamp.HAND_EDITED]
    signed = [(r, v) for r, v in verdicts.items() if str(v).startswith(ADOPTED)]
    fixed = [r for r, v in verdicts.items() if v == RECONCILED]
    if new == cur:
        clean = len(verdicts) - len(dirty) - len(signed)
        plan.noop(path, aid, reason='%d regions clean%s'
                  % (clean, (', %d left alone' % len(dirty)) if dirty else ''))
    else:
        parts = ['%d updated' % len([v for v in verdicts.values()
                                     if v in (stamp.STALE, 'ABSENT')])]
        if fixed:
            parts.append('%d reconciled' % len(fixed))
        plan.write(path, aid, new, verdict=', '.join(parts))
    if dirty:
        plan.skip(path + ' [' + ', '.join(dirty) + ']', aid, stamp.HAND_EDITED,
                  'region hand-edited; left alone. Sign for it with '
                  '`--adopt <region> --because CHG-NNN`, or see what changed with '
                  '`--diff <region>`')
    for rid, v in signed:
        # Still skipped, still never overwritten. The difference is that somebody's name and
        # a change record are on it, which is the whole of what adoption buys.
        plan.skip(path + ' [' + rid + ']', aid, ADOPTED, str(v)[len(ADOPTED) + 1:])


# --------------------------------------------------------------------------- gates

def promise_provenance(given, default):
    """-> 'operator' or 'default'. Who named the first artefact.

    A surface that fills the field with the type's own sentence and posts it looks exactly
    like a person who typed that sentence, and the flag is the only thing standing between
    the two. Comparing against the default is what tells them apart; trusting the presence of
    a value labelled the first real place `operator` when nobody had promised anything.
    """
    given = (given or '').strip()
    return 'operator' if given and given != (default or '').strip() else 'default'


def check_caps(root, tier, plan, answers):
    """The anti-avoidance refusal. Runs before apply, and it is a refusal, not a warning.

    Two rules, and they bind in different places on purpose.

    The TIER REQUIREMENT is about the schema: a data model over twenty notes is a data model
    that will be rewritten before it is ever read. It lifts once the vault has content, or
    once the operator names an artefact and a date.

    The FILE CAPS are about the empty case only, which is the one that cannot be defended:
    a folder with nothing in it receiving seventeen files of structure. Once a vault has
    content, the number of card classes is a judgement, not an arithmetic limit, and it is
    guarded by a refusal that can read ("no class with no work in it") rather than by a
    counter that cannot.
    """
    problems = []
    content = count_content(root)
    named = bool(answers.get('first_artefact'))
    system = len([a for a in plan.actions if a.kind in (fsplan.WRITE, fsplan.COPY)
                  and a.rel.endswith('.md')
                  and (a.rel.startswith('_system') or a.rel == 'CLAUDE.md')])
    # Agents count towards the skills cap. Four agents in an empty vault is the same
    # structure-without-work the cap exists to refuse, and putting them on a different path
    # would have exempted them from it by accident.
    skills = len([a for a in plan.actions
                  if (a.rel.startswith('.claude/skills/') and a.rel.endswith('SKILL.md'))
                  or (a.rel.startswith('.claude/agents/') and a.rel.endswith('.md'))
                  or (a.rel.startswith('.claude/workflows/') and a.rel.endswith('.js'))])

    need = TIER_REQUIRES.get(tier)
    if need and content < need and not named:
        problems.append(
            'tier %s needs %d content files or a named first artefact. This vault has %d '
            'and names none. Either write something first, or say what this vault owes and '
            'by when.' % (tier, need, content))

    if content == 0 and not named:
        cap_sys, cap_skills = TIER_CAPS['light']
        if system > cap_sys or skills > cap_skills:
            problems.append(
                'an empty vault is capped at %d system files and %d skills, and this plan '
                'writes %d and %d. Nothing here has been written yet, so nothing here has '
                'earned a structure this size.' % (cap_sys, cap_skills, system, skills))
    return problems, {'content': content, 'system': system, 'skills': skills}


def build_ledger(plan, answers, arch, tier, deferred):
    from .emit import table
    rows = []
    for a in plan.actions:
        if a.kind == fsplan.MKDIR:
            continue
        rows.append([a.rel, a.artefact, a.kind, a.verdict or '', a.reason or ''])
    body = '\n\n'.join([
        '# Build ledger',
        'Archetype `%s`, tier `%s`, answers in `%s`.' % (arch.name, tier, ANSWERS),
        '## Last plan',
        table(['Path', 'Artefact', 'Action', 'State', 'Note'], rows) or '(nothing)',
        '## Deferred',
        (table(['What', 'Why'], [[d.split(':')[0], ':'.join(d.split(':')[1:]).strip()]
                                 for d in deferred])
         if deferred else
         'None. A deferral is recorded, never assumed: an undeclared deferral is the same '
         'defect as an undeclared write.'),
    ]) + '\n'
    return body
