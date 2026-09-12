# -*- coding: utf-8 -*-
"""14 assertions on the one argument reader the nine runtime scripts share.

WHAT THEY GUARD. `GAP-011`: the scripts validated no argument and accepted no `--help`, in two
different ways, because the rule was written nine times and drifted twice. `mint_change.py
--help` created a directory named `--help` and claimed `CHG-001` in it; `gen_dashboard.py
--check` discarded the flag and wrote the dashboard anyway; `validate_cards.py --help` reported
`BLOCKER 0` over a folder it had never read. All three exited 0.

`AR-11` is the one that keeps this true rather than merely making it true today: it reads every
script the archetypes ship and demands each routes through the reader. A tenth script added
without it is how the second family started.

`AR-14` is the other half. A refusal that also refuses what used to work is not a fix, so every
option each script accepted before the change is run against it and demanded not to be refused.
"""
import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
RUNTIME = os.path.join(PKG, 'runtime')
sys.path.insert(0, RUNTIME)

import _args                                                        # noqa: E402

EXPECTED = 14
NAME = 'args'

USAGE = 'usage: thing.py [<vault>] [--json]\n  what it answers'

# Every script the archetypes ship, with every option it accepted before RES-011.
SHIPPED = {
    'check_agents.py': ['--json'],
    'check_binaries.py': ['--json', '--list'],
    'check_links.py': ['--json', '--orphans'],
    'check_sensitive.py': [],
    'gen_dashboard.py': ['--stdout'],
    'measure_cards.py': ['--json'],
    'mint_change.py': ['--title', 'x', '--date', '2026-01-01'],
    'stamp_check.py': ['--json'],
    'validate_cards.py': ['--json'],
}


def run(args, cwd):
    p = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def group_reader(s):
    cwd = os.path.abspath(os.getcwd())

    root, opts, done = _args.parse([], USAGE, flags=('--json',))
    s.ok('AR-01', 'no argument: the root is the working directory and no option is set',
         done is None and root == cwd and opts == {'--json': False}, repr((root, opts, done)))

    root, _o, done = _args.parse(['sub/dir'], USAGE)
    s.ok('AR-02', 'the first non-option argument is the root, made absolute',
         done is None and root == os.path.abspath('sub/dir'), repr((root, done)))

    for i, flag in enumerate(('--help', '-h')):
        _r, _o, done = _args.parse([flag], USAGE, flags=('--json',))
        s.ok('AR-0%d' % (3 + i), '%s prints the usage and exits 0, doing none of the work'
             % flag, done == (0, USAGE), repr(done))

    _r, _o, done = _args.parse(['--check'], USAGE, flags=('--stdout',))
    s.ok('AR-05', 'an undeclared option is refused by name, with what IS accepted, exit 2',
         done is not None and done[0] == 2 and '--check' in done[1] and '--stdout' in done[1],
         repr(done))

    _r, opts, done = _args.parse(['--json'], USAGE, flags=('--json',))
    s.ok('AR-06', 'a declared flag is set, and the root still defaults',
         done is None and opts['--json'] is True, repr((opts, done)))

    _r, opts, done = _args.parse(['.', '--family', 'CL,AV'], USAGE, values=('--family',))
    s.ok('AR-07', 'a value option takes the next argument, which does not become a second path',
         done is None and opts['--family'] == 'CL,AV', repr((opts, done)))

    _r, _o, done = _args.parse(['--family'], USAGE, values=('--family',))
    s.ok('AR-08', 'a value option given no value is refused by name, exit 2',
         done is not None and done[0] == 2 and '--family' in done[1], repr(done))

    _r, _o, done = _args.parse(['one', 'two'], USAGE)
    s.ok('AR-09', 'two paths are refused, both named: an unquoted argument is the usual cause',
         done is not None and done[0] == 2 and 'one' in done[1] and 'two' in done[1],
         repr(done))

    _r, _o, done = _args.parse([], USAGE, default_root=None)
    s.ok('AR-10', 'a script whose path is required refuses an empty command line, exit 2',
         done == (2, USAGE), repr(done))


def group_shipped(s):
    missing = []
    for name in sorted(SHIPPED):
        text = io.open(os.path.join(RUNTIME, name), encoding='utf-8').read()
        if 'import _args' not in text or 'USAGE = ' not in text:
            missing.append(name)
    s.ok('AR-11', 'every shipped script routes its arguments through the shared reader',
         not missing, 'not wired: %s' % ', '.join(missing))

    tmp = tempfile.mkdtemp(prefix='solai-args-')
    try:
        # The defect itself: a flag the script does not know, on the one that writes by default.
        code, out = run([os.path.join(RUNTIME, 'gen_dashboard.py'), '--check'], tmp)
        s.ok('AR-12', 'gen_dashboard.py --check is refused and writes nothing, where it used '
                      'to discard the flag and write the dashboard anyway',
             code == 2 and not os.path.exists(os.path.join(tmp, 'dashboard.html')),
             repr((code, out[:200], sorted(os.listdir(tmp)))))

        code, out = run([os.path.join(RUNTIME, 'mint_change.py'), '--help'], tmp)
        s.ok('AR-13', 'mint_change.py --help prints usage and creates nothing, where it used '
                      'to make a directory named --help and claim CHG-001 inside it',
             code == 0 and sorted(os.listdir(tmp)) == [],
             repr((code, out[:200], sorted(os.listdir(tmp)))))

        # A refusal that refuses what used to work is not a fix.
        broke = []
        for name, options in sorted(SHIPPED.items()):
            if not options:
                continue
            code, out = run([os.path.join(RUNTIME, name), tmp] + options, tmp)
            if code == 2 and 'unknown option' in out:
                broke.append('%s %s' % (name, ' '.join(options)))
        s.ok('AR-14', 'every option each script accepted before is still accepted',
             not broke, 'refused: %s' % '; '.join(broke))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_reader, group_shipped)
