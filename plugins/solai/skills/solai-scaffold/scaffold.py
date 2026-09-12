# -*- coding: utf-8 -*-
"""Scaffold or re-scaffold a vault. The only entry point that writes.

    py scaffold.py <vault-root> --archetype project --answers key=value ...
    py scaffold.py <vault-root> --archetype role --materials "<file or folder>" ...
    py scaffold.py <vault-root> --apply
    py scaffold.py <vault-root> --rollback
    py scaffold.py <vault-root> --diff <region|path>
    py scaffold.py <vault-root> --adopt <region|path> --because CHG-NNN
    py scaffold.py <vault-root> --from-package

`--plan` is the default and writes nothing. Exit 1 on any refusal.

WHICH DECLARATIONS THIS READS, and it says so on every run. A vault that has been built
before - one carrying `_system/os/answers.toml` - is regenerated from its OWN compiled
declarations in `_system/os/`, not from the package archetype. That is what lets a vault
rename a class, retire one, or change a filename policy and still regenerate truthfully.
Before it, `CLAUDE.md` told its reader to edit the declaration rather than the block, and
the declaration lived in a directory the vault did not have.

A vault built before the engine compiled its manifest in has no `_system/os/manifest.toml`.
The run SYNTHESISES one from the package archetype its answers name, and plans that write as
its own row. The naive alternative - no manifest, therefore package mode - would run a
renamed vault against the package's original classes and write the retired ones back beside
the live ones. That is the exact catastrophe this exists to prevent, performed by the fix.

Emitters and fragments are code and always come from the package; only DECLARATIONS become
vault-local. So an emitter fix reaches every vault on a plain `--apply`, and only a
declaration change needs `--from-package`.

`--from-package` MERGES, it does not replace. The package wins wherever both declare the
same thing, and a class, lookup, agent or workflow this vault declares alone is kept, with its
folder, its projection and its place in the manifest. Replacing whole was the first behaviour
and it deleted `deliverable` from the vault that invented it. The rules and the reasoning are
in `decl.load_merged`.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(HERE))          # .../plugins/solai
sys.path.insert(0, os.path.dirname(PKG))
sys.path.insert(0, PKG)

from lib import decl, engine, fsplan, VERSION  # noqa: E402
from lib.stamp import HAND_EDITED as ST_HAND_EDITED  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')


HEAD_ADOPTED = (
    "# Hand edits somebody has signed for. Each row keeps its region skipped and never\n"
    "# overwritten, exactly as before. What it adds is a name, a date and a change record.\n"
    "# Edit the region again and its sha stops matching, and it reads HAND-EDITED once more.\n")

ROW_ADOPTED = (
    '\n[[adopted]]\n'
    'artefact = "%s"\n'
    'region   = "%s"\n'
    'body-sha = "%s"\n'
    'because  = "%s"\n'
    'date     = "%s"\n')

# A whole file carries no `region`, and that absence is what tells the two apart. It carries one
# thing a region row does not: what the package shipped at the moment of the signature, so that a
# release moving the file afterwards is reported rather than covered by a signature never given
# against it.
ROW_ADOPTED_FILE = (
    '\n[[adopted]]\n'
    'artefact    = "%s"\n'
    'body-sha    = "%s"\n'
    'package-sha = "%s"\n'
    'because     = "%s"\n'
    'date        = "%s"\n')


def parse_argv(argv):
    opts = {'answers': {}, 'only': None, 'force': (), 'mode': 'plan', 'archetype': None,
            'materials': [], 'region': None, 'because': None, 'from_package': False}
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--apply':
            opts['mode'] = 'apply'
        elif a == '--rollback':
            opts['mode'] = 'rollback'
        elif a == '--plan':
            opts['mode'] = 'plan'
        elif a == '--from-package':
            opts['from_package'] = True
        elif a == '--diff':
            opts['mode'] = 'diff'
            i += 1
            opts['region'] = argv[i]
        elif a == '--adopt':
            opts['mode'] = 'adopt'
            i += 1
            opts['region'] = argv[i]
        elif a == '--because':
            i += 1
            opts['because'] = argv[i]
        elif a == '--archetype':
            i += 1
            opts['archetype'] = argv[i]
        elif a == '--materials':
            # Repeatable. Documents prepared for the new place: copied in, never read here.
            i += 1
            opts['materials'].append(argv[i])
        elif a == '--only':
            i += 1
            opts['only'] = set(argv[i].split(','))
        elif a == '--force':
            i += 1
            opts['force'] = tuple(argv[i].split(','))
        elif a == '--answers':
            i += 1
            while i < len(argv) and '=' in argv[i]:
                k, _, v = argv[i].partition('=')
                opts['answers'][k] = v.split('|') if '|' in v else v
                i += 1
            continue
        elif not a.startswith('--'):
            positional.append(a)
        i += 1
    opts['root'] = os.path.abspath(positional[0]) if positional else os.getcwd()
    return opts


def _plan_rows(root, pkg, answers, arch, o):
    """Every row a plain run would produce -> {path: action}. Writes nothing.

    The plan is the authority on what state a file is in, so `--adopt <path>` asks it rather
    than classifying the file a second time in here. A second classifier is how the engine
    grew two answers to one question twice already.
    """
    result = engine.Result()
    plan, _L, _tier = engine.build_plan(root, pkg, answers, arch, result)
    return {a.rel: a for a in plan.actions}


SIGNABLE = ('FOREIGN', 'LOCAL', ST_HAND_EDITED)


def file_mode(root, pkg, answers, arch, o):
    """`--diff <path>` and `--adopt <path> --because CHG-NNN`, for a whole file.

    The same word as the region verb and the same promise: the file stays skipped and is never
    overwritten. What the signature adds is a name, a date and a change record, in place of a
    row that says the engine cannot tell whose the file is.
    """
    import difflib
    from lib import stamp as ST

    path = o['region'].replace(os.sep, '/')
    row = _plan_rows(root, pkg, answers, arch, o).get(path)
    if row is None:
        print('  nothing in this vault\'s plan is called %r.' % path)
        return 1

    here = fsplan.read(os.path.join(root, path.replace('/', os.sep)))
    if here is None:
        print('  %s does not exist, so there is nothing to sign for.' % path)
        return 1

    if o['mode'] == 'diff':
        if not row.content:
            print('  %s [%s] %s' % (path, row.verdict, row.reason))
            print('  no diff for this one: it is generated rather than copied, and the body it '
                  'would be compared against is built inside the plan. --adopt still applies.')
            return 1
        shipped = fsplan.read(row.content)
        print()
        print('%s   %s' % (path, row.verdict))
        if shipped is None:
            print('  the package ships no such file any more.')
            return 0
        if ST.normalise(here) == ST.normalise(shipped):
            print('  identical to what the package ships.')
            return 0
        for line in difflib.unified_diff(here.split('\n'), shipped.split('\n'),
                                         'in the vault', 'from the package', lineterm=''):
            print('  ' + line)
        return 0

    if not o['because']:
        print('  --adopt needs --because CHG-NNN. A divergence with no record behind it '
              'is the state adoption exists to end, not one to write down.')
        return 1
    if row.verdict not in SIGNABLE:
        print('  %s reads %s, so there is nothing to sign for. Adoption is for a file this '
              'vault keeps against what the package ships.' % (path, row.verdict or row.kind))
        return 1

    art = None
    for a in arch.artefacts:
        if a.get('path') == path:
            art = a
    volatile = (art or {}).get('volatile')
    target = os.path.join(root, '_system', 'os', 'adopted.toml')
    head = '' if os.path.exists(fsplan.w(target)) else HEAD_ADOPTED
    out = ROW_ADOPTED_FILE % (path, ST.body_sha(here, volatile), row.src or '',
                              o['because'], engine._today())
    with open(fsplan.w(target), 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(head + out)
    print('  adopted %s under %s. Still skipped, still never overwritten.'
          % (path, o['because']))
    return 0


def _rendered_regions(root, pkg, answers, arch):
    """Every generated region a run would produce -> {(path, region id): text}.

    Built by planning and writing nothing. The plan is the authority on what a region would
    contain, so asking it is the only way `--diff` can be trusted not to describe something
    the apply would not do.
    """
    out = {}
    result = engine.Result()
    engine.build_plan(root, pkg, answers, arch, result)
    for path, regs in result.regions.items():
        for rid, text in regs.items():
            out[(path, rid)] = text
    return out


def region_mode(root, pkg, answers, arch, o):
    """`--diff <region>` and `--adopt <region> --because CHG-NNN`.

    Neither exists to make a hand edit go away. `--diff` answers the question a dirty region
    could not answer before - what was changed - and `--adopt` records that somebody has
    taken responsibility for it, without touching the region or its marker. An adopted
    region is still skipped and still never overwritten.
    """
    import difflib
    from lib import regions as R, stamp as ST

    rid = o['region']
    wanted = _rendered_regions(root, pkg, answers, arch)
    hits = sorted({path for (path, r) in wanted if r == rid})
    if not hits:
        # Not a region: a whole file, which takes the same two verbs and the same word.
        if '/' in rid or '.' in rid:
            return file_mode(root, pkg, answers, arch, o)
        print('  no generated region %r. Known: %s'
              '\n  A whole file is named by its path, e.g. _system/scripts/thing.py'
              % (rid, ', '.join(sorted({r for _, r in wanted}))))
        return 1

    for path in hits:
        text = fsplan.read(os.path.join(root, path.replace('/', os.sep)))
        if text is None:
            print('  %s does not exist yet, so there is nothing to compare.' % path)
            continue
        found = R.find_all(text).get(rid)
        if found is None:
            print('  %s carries no region %r.' % (path, rid))
            continue
        now, would = found.content.strip(), wanted[(path, rid)].strip()

        if o['mode'] == 'diff':
            print()
            print('%s [%s]   %s' % (path, rid, found.verdict(None)))
            if now == would:
                print('  identical to what the declarations produce.')
                continue
            for line in difflib.unified_diff(now.split('\n'), would.split('\n'),
                                             'in the vault', 'from the declarations',
                                             lineterm=''):
                print('  ' + line)
            continue

        if not o['because']:
            print('  --adopt needs --because CHG-NNN. A divergence with no record behind it '
                  'is the state adoption exists to end, not one to write down.')
            return 1
        if found.verdict(None) != ST.HAND_EDITED:
            print('  %s [%s] is not hand-edited, so there is nothing to adopt.' % (path, rid))
            return 1
        target = os.path.join(root, '_system', 'os', 'adopted.toml')
        head = '' if os.path.exists(fsplan.w(target)) else HEAD_ADOPTED
        row = ROW_ADOPTED % (path, rid, ST.body_sha(found.content), o['because'],
                             engine._today())
        with open(fsplan.w(target), 'a', encoding='utf-8', newline='\n') as fh:
            fh.write(head + row)
        print('  adopted %s [%s] under %s. Still skipped, still never overwritten.'
              % (path, rid, o['because']))
    return 0


def main():
    o = parse_argv(sys.argv[1:])
    root = o['root']
    print('solai %s   %s' % (VERSION, root))

    if o['mode'] == 'rollback':
        res, err = fsplan.rollback(os.path.join(root, engine.MANIFEST.replace('/', os.sep)))
        if err:
            print('  ' + err)
            return 1
        print('  restored %(restored)d, removed %(removed)d, unrecoverable %(unrecoverable)d'
              % res)
        return 1 if res['unrecoverable'] else 0

    if not fsplan.exists(root):
        print('  no such directory: %s' % root)
        return 1

    answers = engine.read_answers(os.path.join(root, engine.ANSWERS.replace('/', os.sep)))
    answers.update(o['answers'])
    answers.setdefault('today', engine._today())
    answers.setdefault('name', os.path.basename(root))
    archetype = o['archetype'] or answers.get('archetype')
    if not archetype:
        print('  no archetype. Pass --archetype, or run the setup through /solai new.')
        return 1
    answers['archetype'] = archetype

    # ---------------------------------------------------------------- which declarations
    # Vault-local iff this vault has been built before. `answers.toml` is the test rather
    # than the presence of `_system/os/classes/`, because `minimal` declares no classes at
    # all and would otherwise be misread as a first build every time.
    built_before = os.path.exists(os.path.join(root, engine.ANSWERS.replace('/', os.sep)))
    compiled = os.path.join(root, '_system', 'os', 'manifest.toml')
    notes = []
    try:
        if built_before and not o['from_package'] and os.path.exists(compiled):
            arch, notes = decl.load_compiled(root)
            print('  declarations: this vault  (_system/os)')
        elif o['from_package'] and built_before:
            # An upgrade MERGES rather than replaces. The package wins everywhere the two
            # declare the same thing, and a declaration this vault alone carries is kept -
            # class, lookup, agent or workflow - because re-importing whole used to delete it
            # along with its folder and its projection.
            arch, notes = decl.load_merged(PKG, root, archetype)
            print('  declarations: package  (archetypes/%s), re-imported on request; %d '
                  'declared only by this vault, kept: %s'
                  % (archetype, len(arch.kept), ', '.join(arch.kept) or 'none'))
        else:
            arch = decl.load_archetype(PKG, archetype)
            if built_before:
                print('  declarations: package  (archetypes/%s), and this vault has no '
                      'compiled manifest yet. This plan writes one; the run after this '
                      'reads the compiled copy.' % archetype)
            else:
                print('  declarations: package  (archetypes/%s), first build' % archetype)
    except decl.DeclError as e:
        print('  the declarations do not hold together, so nothing was written:')
        print(e)
        return 1
    for n in notes:
        print('  note: %s' % n)

    answers.setdefault('governance_tier', arch.default_tier)
    answers.setdefault('output_language', 'en')
    answers.setdefault('output_language_name',
                       {'ru': 'Russian', 'en': 'English'}.get(answers['output_language'],
                                                              answers['output_language']))
    answers.setdefault('remit', arch.defaults.get('remit', 'Unknown'))
    answers.setdefault('content_languages', answers['output_language'])
    answers.setdefault('filename_language',
                       arch.defaults.get('filename_language', 'english'))
    # Whoever named it matters as much as what it says: the artefact is the denominator
    # of every ratio this place reports, and a default is a sentence nobody promised.
    first_default = arch.defaults.get('first_artefact', '')
    answers['first_artefact_by'] = engine.promise_provenance(
        answers.get('first_artefact'), first_default)
    answers.setdefault('first_artefact', first_default)
    answers.setdefault('changes_folder', arch.defaults.get('changes_folder', 'changes'))

    # The interview asks where the work already lives, on the grounds that "counting what
    # already exists is the difference between a plan and a guess". Until this it asked and
    # discarded the answer, so the count existed once in a conversation and nowhere after.
    # It is recorded in the bond, beside the bootstrap ratio it puts in proportion: thirty
    # system files against zero content reads very differently next to a corpus of 2130.
    corpus = (answers.get('corpus') or '').strip()
    if corpus and os.path.isdir(fsplan.w(corpus)):
        n = 0
        for _dir, dirnames, filenames in os.walk(fsplan.w(corpus)):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            n += len([f for f in filenames if not f.startswith('.')])
        answers['corpus_files'] = n
        print('  corpus: %d files at %s' % (n, corpus))
    elif corpus:
        # D13: absence is a value. A path that is not there is reported, never counted as 0.
        answers['corpus_files'] = 'Unknown'
        print('  corpus: %s is not a directory this machine can see. Recorded as Unknown.'
              % corpus)

    if o['mode'] in ('diff', 'adopt'):
        return region_mode(root, PKG, answers, arch, o)

    result = engine.Result()
    plan, L, tier = engine.build_plan(root, PKG, answers, arch, result,
                                      only=o['only'], force=o['force'],
                                      materials=tuple(o['materials']))

    problems, counts = engine.check_caps(root, tier, plan, answers)

    print()
    print(plan.table())
    if result.errors:
        print('\nerrors:')
        for e in result.errors:
            print('  %s' % e)
    if result.deferred:
        print('\ndeferred (recorded, not assumed):')
        for d in result.deferred:
            print('  %s' % d)
    if problems:
        print('\nrefused:')
        for p in problems:
            print('  %s' % p)
    hand = plan.blockers()
    if hand:
        print('\nhand-edited, left alone:')
        for a in hand:
            print('  %s' % a.rel)

    print('\ncontent %d   system files this plan writes %d   skills %d   tier %s'
          % (counts['content'], counts['system'], counts['skills'], tier))

    if o['mode'] != 'apply':
        print('\nplan only. Nothing written. Re-run with --apply.')
        return 1 if (problems or result.errors) else 0

    if problems or result.errors:
        print('\nnot applied.')
        return 1

    if plan.is_noop():
        print('\nnothing to do: every artefact is already what the declarations say.')
        return 0

    manifest = os.path.join(root, engine.MANIFEST.replace('/', os.sep))
    backup = os.path.join(root, engine.BACKUP.replace('/', os.sep))
    manifest_data = engine.fsplan.apply(plan, manifest, backup_dir=backup)

    engine.write_answers(os.path.join(root, engine.ANSWERS.replace('/', os.sep)), answers)
    ledger = engine.build_ledger(plan, answers, arch, tier, result.deferred)
    lp = os.path.join(root, engine.BUILD_LEDGER.replace('/', os.sep))
    with open(fsplan.w(lp), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(ledger)

    # The dashboard reflects the vault AFTER the apply, so it cannot be part of the plan.
    # It is appended to the manifest anyway: a file this run created that rollback could not
    # remove would be a write outside the record, which is the one thing the manifest is for.
    dash = os.path.join(root, '_system', 'scripts', 'gen_dashboard.py')
    if os.path.exists(fsplan.w(dash)):
        import json
        import subprocess
        existed = fsplan.exists(os.path.join(root, 'dashboard.html'))
        subprocess.run([sys.executable, dash, root], capture_output=True)
        if not existed and fsplan.exists(os.path.join(root, 'dashboard.html')):
            manifest_data['actions'].append(
                {'path': 'dashboard.html', 'artefact': 'dashboard', 'kind': 'WRITE',
                 'pre': {'existed': False}})
            with open(fsplan.w(manifest), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(json.dumps(manifest_data, ensure_ascii=False, indent=2))

    c = plan.counts
    print('\napplied. %s' % '  '.join('%s %d' % (k, v) for k, v in sorted(c.items())))
    print('ledger: %s' % engine.BUILD_LEDGER)
    return 0


if __name__ == '__main__':
    sys.exit(main())
