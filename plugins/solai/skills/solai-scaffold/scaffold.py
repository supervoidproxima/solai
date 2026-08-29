# -*- coding: utf-8 -*-
"""Scaffold or re-scaffold a vault. The only entry point that writes.

    py scaffold.py <vault-root> --archetype project --answers key=value ...
    py scaffold.py <vault-root> --archetype role --materials "<file or folder>" ...
    py scaffold.py <vault-root> --apply
    py scaffold.py <vault-root> --rollback

`--plan` is the default and writes nothing. Exit 1 on any refusal.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(HERE))          # .../plugins/solai
sys.path.insert(0, os.path.dirname(PKG))
sys.path.insert(0, PKG)

from lib import decl, engine, fsplan, VERSION  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')


def parse_argv(argv):
    opts = {'answers': {}, 'only': None, 'force': (), 'mode': 'plan', 'archetype': None,
            'materials': []}
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

    try:
        arch = decl.load_archetype(PKG, archetype)
    except decl.DeclError as e:
        print('  the declarations do not hold together, so nothing was written:')
        print(e)
        return 1

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
