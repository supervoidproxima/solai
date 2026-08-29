# -*- coding: utf-8 -*-
"""Read an existing vault and report where it stands against the canon. Writes nothing.

    py probe.py <vault-root> [--json] [--report <path>]

Order matters: **count first**. A conformance verdict handed down before anyone has counted
the files is an opinion about a vault the tool has not met.

Nine probes. Every finding carries a path, or a count of paths, or it is not emitted.

    P1  root markers                what infrastructure already exists
    P2  governance layer            charter, registry, schemas: which tier this already is
    P3  card classes                inferred from what is on disk, not from a template
    P4  frontmatter key census      including violations of the kebab rule
    P5  tag census                  in use versus declared
    P6  change discipline           records, numbering, immutability signals
    P7  skills                      vault-local and global, and which classes lack one
    P8  generated-file honesty      files claiming to be generated with no stamp
    P9  stamp census                any existing place bond, which makes this an upgrade

The report always ends with what was NOT checked. A conformance report with no such section
is claiming coverage it does not have, which is the failure this whole package is built to
avoid.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules', '__pycache__', '.claude',
             'venv', '.venv'}
ID_RX = re.compile(r'^([A-Z]{2,4})-(\d{2,4})$')
KEY_RX = re.compile(r'^([A-Za-z_][A-Za-z0-9_.-]*):', re.M)

NOT_CHECKED = [
    ('semantic correctness of any `type:` value',
     'whether a note is really an analysis or really a source is a judgement, not a pattern'),
    ('whether a change record was owed and never written',
     'only a proxy is mechanical: a convention file changed with no record dated after it'),
    ('whether prose agrees with frontmatter',
     'needs reading, not scanning. The status protocol exists because this cannot be checked'),
    ('link direction sanity',
     'a link that resolves may still point the wrong way; the reciprocity check catches only '
     'declared pairs'),
    ('whether a folder is still in use',
     'age of last edit is reported, but "in use" is a decision about intent'),
]


# --------------------------------------------------------------------------- reading

def split_fm(text):
    if not text.startswith('---'):
        return None
    nl = text.find('\n')
    if nl == -1 or text[3:nl].strip():
        return None
    end = text.find('\n---', nl)
    return text[nl + 1:end] if end != -1 else None


def scalar(fm, key):
    if not fm:
        return None
    m = re.search(r'^%s:[ \t]*(.*?)[ \t]*$' % re.escape(key), fm, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    return v.strip('"\'') if v else None


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield dirpath, name


def load(root):
    """One pass. Everything else works off this."""
    files = []
    for dirpath, name in walk(root):
        path = os.path.join(dirpath, name)
        rel = os.path.relpath(path, root).replace(os.sep, '/')
        rec = {'rel': rel, 'name': name, 'ext': os.path.splitext(name)[1].lower(),
               'stem': os.path.splitext(name)[0],
               'dir': os.path.dirname(rel) or '.', 'fm': None, 'type': None,
               'status': None, 'keys': [], 'size': 0, 'text_head': ''}
        try:
            rec['size'] = os.path.getsize(path)
        except OSError:
            pass
        if rec['ext'] == '.md':
            try:
                with io.open(path, encoding='utf-8') as fh:
                    head = fh.read(6000)
                rec['text_head'] = head
                fm = split_fm(head)
                rec['fm'] = fm
                rec['keys'] = KEY_RX.findall(fm) if fm else []
                rec['type'] = scalar(fm, 'type')
                rec['status'] = scalar(fm, 'status')
            except (OSError, UnicodeDecodeError):
                pass
        files.append(rec)
    return files


# --------------------------------------------------------------------------- probes

def p1_markers(root, files):
    marks = {}
    for m in ('CLAUDE.md', '_system', '.obsidian', '.claude/skills', 'changes', '_changes'):
        marks[m] = os.path.exists(os.path.join(root, m.replace('/', os.sep)))
    marks['*.base'] = any(f['ext'] == '.base' for f in files)
    return marks


def p2_governance(root):
    org = os.path.join(root, '_system', 'org')
    found, versions = {}, {}
    for name, key in (('charter.md', 'charter-version'), ('registry.md', 'registry-version'),
                      ('schemas.md', 'schema-version'), ('impact.md', None),
                      ('counsel-log.md', None)):
        p = os.path.join(org, name)
        found[name] = os.path.exists(p)
        if found[name] and key:
            try:
                with io.open(p, encoding='utf-8') as fh:
                    versions[name] = scalar(split_fm(fh.read(3000)), key)
            except (OSError, UnicodeDecodeError):
                pass
    has_dict = any(os.path.exists(os.path.join(root, '_system', n)) for n in
                   ('DATA-DICTIONARY.md', 'data-dictionary.md'))
    if found['charter.md'] and found['registry.md']:
        tier = 'governed'
    elif has_dict:
        tier = 'standard'
    else:
        tier = 'light'
    return {'files': found, 'versions': versions, 'observed_tier': tier}


def p3_classes(files, sample=20):
    """Infer a card class per folder. A key in 95%+ of samples is required; a scalar with
    8 or fewer distinct values across 10+ cards is an enum."""
    by_dir = {}
    for f in files:
        if f['ext'] != '.md':
            continue
        # `_`-prefixed files are infrastructure by convention (`_template.md`, `_index.md`).
        # Counting them in the denominator hid a real class: 3 RX cards beside one template
        # is 75%, under the threshold, so `wellbeing/prescriptions/` went undetected.
        if f['name'].startswith('_'):
            continue
        by_dir.setdefault(f['dir'], []).append(f)
    out = []
    for d, group in sorted(by_dir.items()):
        # Only engine state is excluded, not all of `_system`. A blanket exclusion hides
        # real card folders that happen to live there, such as decision records.
        if len(group) < 3 or d.startswith('_system/os'):
            continue
        ided = [f for f in group if ID_RX.match(f['stem'])]
        if len(ided) < max(3, 0.8 * len(group)):
            continue
        prefixes = {}
        for f in ided:
            prefixes.setdefault(ID_RX.match(f['stem']).group(1), []).append(f)
        prefix, members = max(prefixes.items(), key=lambda kv: len(kv[1]))
        types = {}
        for f in members:
            if f['type']:
                types[f['type']] = types.get(f['type'], 0) + 1
        picked = sorted(members, key=lambda f: f['stem'])[:sample]
        key_count, val_sets, statuses = {}, {}, {}
        for f in picked:
            for k in set(f['keys']):
                key_count[k] = key_count.get(k, 0) + 1
            for k in set(f['keys']):
                v = scalar(f['fm'], k)
                if v and not v.startswith(('[', '"[[')):
                    val_sets.setdefault(k, set()).add(v)
        for f in members:
            if f['status']:
                statuses[f['status']] = statuses.get(f['status'], 0) + 1
        n = len(picked)
        required = sorted(k for k, c in key_count.items() if n and c / n >= 0.95)
        optional = sorted(k for k, c in key_count.items() if n and 0.05 <= c / n < 0.95)
        enums = {k: sorted(v) for k, v in val_sets.items()
                 if 1 < len(v) <= 8 and len(picked) >= 10 and k != 'id'}
        nums = sorted(int(ID_RX.match(f['stem']).group(2)) for f in members)
        holes = [x for x in range(1, max(nums) + 1) if x not in nums] if nums else []
        out.append({
            'folder': d, 'prefix': prefix, 'cards': len(members),
            'type': max(types, key=types.get) if types else None,
            'type_consistent': len(types) <= 1,
            'required': required, 'optional': optional, 'enums': enums,
            'statuses': statuses, 'sampled': n,
            'id_holes': holes[:12], 'id_hole_count': len(holes),
        })
    return out


def _shape(fm, key):
    """'list' or 'scalar'. A key's shape is what decides whether two similar names are two
    names for one concept or two different concepts."""
    if not fm:
        return None
    m = re.search(r'^%s:[ \t]*(.*?)[ \t]*$' % re.escape(key), fm, re.M)
    if not m:
        return None
    rest = m.group(1).strip()
    if rest.startswith('['):
        return 'list'
    if rest:
        return 'scalar'
    for line in fm.split('\n')[fm.split('\n').index(m.group(0)) + 1:] \
            if m.group(0) in fm.split('\n') else []:
        if not line.strip():
            continue
        if line.startswith((' ', '\t')):
            return 'list' if re.match(r'^\s*-\s+', line) else 'map'
        break
    return 'scalar'


def p4_keys(files):
    census, underscore, per_key_files, shapes = {}, {}, {}, {}
    for f in files:
        for k in set(f['keys']):
            census[k] = census.get(k, 0) + 1
            per_key_files.setdefault(k, []).append(f['rel'])
            s = _shape(f['fm'], k)
            if s:
                shapes.setdefault(k, {})[s] = shapes.setdefault(k, {}).get(s, 0) + 1
            if '_' in k:
                underscore[k] = underscore.get(k, 0) + 1

    def dominant(k):
        d = shapes.get(k) or {}
        return max(d, key=d.get) if d else None

    # A plural beside its singular is only a duplicate when both hold the same SHAPE of
    # value. `sources: [a, b]` and `source: "[[x]]"` are a collection and a pointer, two
    # concepts that happen to share a stem, and flagging them trains the reader to ignore
    # this row. Fangorn surfaced four such pairs, all of them legitimate.
    plural_pairs, plural_ambiguous = [], []
    for k in census:
        if not (k.endswith('s') and k[:-1] in census):
            continue
        sing = k[:-1]
        row = (k, sing, census[k], census[sing], dominant(k) or '?', dominant(sing) or '?')
        if dominant(k) and dominant(k) == dominant(sing):
            plural_pairs.append(row)
        else:
            plural_ambiguous.append(row)
    singles = sorted(k for k, c in census.items() if c == 1)
    return {'census': census, 'underscore': underscore,
            'underscore_files': {k: per_key_files[k][:6] for k in underscore},
            'plural_pairs': plural_pairs, 'plural_ambiguous': plural_ambiguous,
            'used_once': singles}


def p5_tags(root, files):
    used = {}
    for f in files:
        if not f['fm']:
            continue
        m = re.search(r'^tags:[ \t]*(.*?)[ \t]*$', f['fm'], re.M)
        if not m:
            continue
        rest = m.group(1).strip()
        vals = []
        if rest.startswith('[') and rest.endswith(']'):
            inner = rest[1:-1].strip()
            vals = [x.strip().strip('"\'') for x in inner.split(',')] if inner else []
        else:
            started = False
            for line in f['fm'].split('\n'):
                if line.startswith('tags:'):
                    started = True
                    continue
                if started:
                    if line.startswith((' ', '\t')):
                        im = re.match(r'^\s*-\s+(.*?)\s*$', line)
                        if im:
                            vals.append(im.group(1).strip().strip('"\''))
                    elif line.strip():
                        break
        for v in vals:
            if v:
                used[v] = used.get(v, 0) + 1
    # Find the vocabulary by what it is about, not by an exact filename. Fangorn's is
    # `_system/Tag vocabulary.md`, which a fixed list of names missed entirely, and the
    # report then said "no declared list found" about a vault that has one.
    declared, sources = set(), []
    sysdir = os.path.join(root, '_system')
    if os.path.isdir(sysdir):
        for dirpath, dirnames, filenames in os.walk(sysdir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                low = name.lower()
                if not low.endswith('.md'):
                    continue
                if not ('tag' in low or 'vocab' in low or 'properties' in low):
                    continue
                p = os.path.join(dirpath, name)
                try:
                    with io.open(p, encoding='utf-8') as fh:
                        declared |= set(re.findall(r'`([^`\s]+)`', fh.read()))
                    sources.append(os.path.relpath(p, root).replace(os.sep, '/'))
                except (OSError, UnicodeDecodeError):
                    pass
    return {'used': used, 'declared': sorted(declared), 'declared_in': sources,
            'undeclared': sorted(t for t in used if declared and t not in declared)}


def p6_changes(root, files):
    for folder in ('changes', '_changes', '_project management/changes'):
        recs = [f for f in files if f['dir'] == folder and f['ext'] == '.md']
        if recs:
            nums = sorted(int(m.group(1)) for m in
                          (re.match(r'^CHG-(\d+)$', f['stem']) for f in recs) if m)
            holes = [x for x in range(1, max(nums) + 1) if x not in nums] if nums else []
            with_affects = len([f for f in recs if f['fm'] and 'affects' in f['fm']])
            return {'folder': folder, 'records': len(recs), 'numbered': len(nums),
                    'holes': holes[:10], 'hole_count': len(holes),
                    'with_affects': with_affects}
    return {'folder': None, 'records': 0}


def p7_skills(root, files, classes):
    local = []
    sd = os.path.join(root, '.claude', 'skills')
    if os.path.isdir(sd):
        for name in sorted(os.listdir(sd)):
            if os.path.exists(os.path.join(sd, name, 'SKILL.md')):
                local.append(name)
    glob = []
    gd = os.path.join(os.path.expanduser('~'), '.claude', 'skills')
    vault_name = os.path.basename(os.path.abspath(root))
    if os.path.isdir(gd):
        for name in sorted(os.listdir(gd)):
            p = os.path.join(gd, name, 'SKILL.md')
            if not os.path.exists(p):
                continue
            try:
                with io.open(p, encoding='utf-8') as fh:
                    head = fh.read(1200)
            except (OSError, UnicodeDecodeError):
                continue
            if 'scope: local' in head or vault_name.lower() in head.lower():
                glob.append(name)
    return {'vault_local': local, 'global_scoped': glob,
            'classes_without_skill': [c['prefix'] for c in classes
                                      if not any(c['folder'].rstrip('/').split('/')[-1]
                                                 .startswith(s[:4]) for s in local + glob)]}


def p8_honesty(files):
    """Files that claim, ABOUT THEMSELVES, to be generated, and carry no stamp.

    The first draft matched the word "generated" anywhere in the first 4 KB and returned 41
    files on Fangorn, most of them hand-written prose that merely discusses generation: its
    charter states "the generator reads the field, not the prose" and was duly accused of
    being generated. A probe that is wrong 40 times out of 41 trains its reader to skip the
    row, which is worse than not having it.

    So the claim has to be self-referential: shouted in the frontmatter title, or made in
    the opening lines of the body, or phrased as an instruction not to edit the file.
    """
    SHOUT = re.compile(r'GENERATED|AUTOGENERATED|АВТОГЕНЕР')
    DONT_EDIT = re.compile(
        r'(do not|don\'t|never)\s+(hand[- ])?edit|hand[- ]edit\w*\s+(is|are)\s+'
        r'(a\s+)?(defect|error)|не\s+редактир|правки\s+-\s+в\s+карточки', re.I)
    out = []
    for f in files:
        if f['ext'] not in ('.md', '.base') or not f['text_head']:
            continue
        if 'body-sha' in (f['fm'] or ''):
            continue
        fm = f['fm'] or ''
        body_lines = [l for l in f['text_head'][len(fm):].split('\n') if l.strip()][:4]
        opening = '\n'.join(body_lines)
        if SHOUT.search(fm) or SHOUT.search(opening) or DONT_EDIT.search(opening):
            out.append(f['rel'])
    return out


def p9_stamps(root, files):
    bond = os.path.join(root, '_system', 'os', 'vault.md')
    stamped = [f['rel'] for f in files if f['fm'] and 'body-sha' in f['fm']]
    return {'bond': os.path.exists(bond), 'stamped_files': len(stamped)}


# --------------------------------------------------------------------------- verdict

def propose_tier(counts, gov, classes):
    content = counts['content']
    if gov['observed_tier'] == 'governed':
        return 'governed', 'the org layer already exists here'
    if classes and content >= 150:
        return 'standard', ('%d content files and %d inferred card classes: a data model is '
                            'already in use, whether or not it is written down'
                            % (content, len(classes)))
    if classes:
        return 'standard', '%d inferred card classes already in use' % len(classes)
    if content >= 20:
        return 'light', '%d content files, no card classes in evidence' % content
    return 'light', 'small vault, nothing here needs a schema yet'


def run(root):
    files = load(root)
    md = [f for f in files if f['ext'] == '.md']
    content = [f for f in md if not f['dir'].startswith('_system') and f['name'] != 'CLAUDE.md']
    classes = p3_classes(files)
    counts = {
        'files': len(files), 'md': len(md), 'content': len(content),
        'folders': len({f['dir'] for f in files}),
        'with_frontmatter': len([f for f in md if f['fm']]),
        'types': len({f['type'] for f in md if f['type']}),
        'cards': sum(c['cards'] for c in classes),
    }
    gov = p2_governance(root)
    tier, why = propose_tier(counts, gov, classes)
    return {
        'root': os.path.abspath(root), 'counts': counts,
        'p1': p1_markers(root, files), 'p2': gov, 'p3': classes, 'p4': p4_keys(md),
        'p5': p5_tags(root, md), 'p6': p6_changes(root, files),
        'p7': p7_skills(root, files, classes), 'p8': p8_honesty(files),
        'p9': p9_stamps(root, md),
        'proposed_tier': tier, 'tier_reason': why,
        'not_checked': NOT_CHECKED,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = os.path.abspath(args[0]) if args else os.getcwd()
    data = run(root)
    if '--json' in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=list))
        return 0
    import report
    text = report.render(data)
    if '--report' in sys.argv:
        out = sys.argv[sys.argv.index('--report') + 1]
        parent = os.path.dirname(os.path.abspath(out))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        print('report written: %s' % out)
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
