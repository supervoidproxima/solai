# -*- coding: utf-8 -*-
"""11 assertions on the personal-identifier guard and the ignore rule it ships with.

Every one of them is shaped by a failure that already happened in a vault this package built.
`CHG-134` there: a sync client's conflict copy, untracked, carrying 728 children's national
identifiers, with `git check-ignore` refusing to claim it because the ignore rule named the
page it copied by its exact filename. `CHG-146`: a second guard that reported 43 of 194
affected files, because it could only ever see 43.

SN-04 is the one that matters most and it is the easiest to get wrong: the checker must never
print an identifier it found. A guard that writes them into a terminal, a CI log or a dated run
report has published the thing it exists to protect.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, 'runtime'))

import check_sensitive as CS                                        # noqa: E402

EXPECTED = 11
NAME = 'sensitive'

IIN = '030512500123'
CARD = '4111111111111111'


def _vault(tmp, files, git=True):
    root = os.path.join(tmp, 'v')
    os.makedirs(root, exist_ok=True)
    for rel, body in files.items():
        p = os.path.join(root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, 'w', encoding='utf-8', newline='\n').write(body)
    if git:
        q = {'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
        subprocess.run(['git', 'init', '-q'], cwd=root, **q)
        subprocess.run(['git', 'add', 'tracked.md'], cwd=root, **q)
    return root


def _run(root):
    """Run main() the way a user does, capturing what it prints."""
    import io as _io
    buf, old, argv = _io.StringIO(), sys.stdout, sys.argv
    sys.stdout, sys.argv = buf, ['check_sensitive', root]
    try:
        code = CS.main()
    finally:
        sys.stdout, sys.argv = old, argv
    return code, buf.getvalue()


def group_patterns(s):
    hits = {n: len(set(rx.findall('id %s and %s' % (IIN, CARD)))) for n, rx, _, _ in CS.PATTERNS}
    s.ok('SN-01', 'a twelve-digit identifier and a card number are both recognised',
         hits['national-id-12'] == 1 and hits['card-16'] == 1, repr(hits))

    long_run = 'build 1234567890123456789 end'
    s.eq('SN-02', 'a longer digit run is not mistaken for a twelve-digit identifier',
         len(set(CS.PATTERNS[0][1].findall(long_run))), 0)

    s.ok('SN-03', 'a date and an ordinary number are not identifiers',
         not CS.PATTERNS[0][1].findall('2026-09-12 and 41 files and 1416 scanned'),
         'a guard that cries wolf on every number is turned off by the second run')


def group_states(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-sn-')
    try:
        root = _vault(tmp, {
            'tracked.md': 'iin %s\niin 030512500124\niin 030512500125\n' % IIN,
            'exposed.md': 'iin %s\niin 030512500126\niin 030512500127\n' % IIN,
            'ignored.md': 'iin %s\niin 030512500128\niin 030512500129\n' % IIN,
            '.gitignore': 'ignored.md\n',
            'photo.png': 'not text',
        })
        code, out = _run(root)

        s.ok('SN-04', 'the report never prints an identifier it found',
             IIN not in out and '030512500126' not in out,
             'a guard that echoes what it found has published it')

        s.ok('SN-05', 'an untracked, unignored file carrying identifiers is RED and is the '
                      'exit code',
             code == 1 and 'SENSITIVE RED' in out and 'exposed.md' in out, repr(code))

        s.ok('SN-06', 'a tracked file is reported separately, as a decision someone made',
             'TRACKED' in out and 'tracked.md' in out, 'tracked is not the dangerous state')

        s.ok('SN-07', 'a file an ignore rule covers is reported as having no path to a commit',
             'ignored' in out and 'ignored.md' in out, repr(out[-400:]))

        s.ok('SN-08', 'a binary is counted as not checked rather than passed over in silence',
             'not checked' in out and 'photo.png' not in out,
             'a checker that skips binaries while reporting green claims coverage it lacks')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_clean(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-sn2-')
    try:
        root = _vault(tmp, {'tracked.md': 'no identifiers here, only prose and 41 files\n'})
        code, out = _run(root)
        s.ok('SN-09', 'a vault holding no identifiers is green and exits zero',
             code == 0 and 'SENSITIVE GREEN' in out, repr(out[-200:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_shipped_rule(s):
    """The seeded `.gitignore` is half of the answer; these two say which half."""
    tmp = tempfile.mkdtemp(prefix='solai-test-sn3-')
    try:
        frag = io.open(os.path.join(PKG, 'common', 'fragments', 'system', 'gitignore.txt'),
                       encoding='utf-8').read()
        rows = 'iin %s\niin 030512500131\niin 030512500132\n' % IIN
        root = _vault(tmp, {
            '.gitignore': frag,
            'tracked.md': 'nothing here\n',
            'data/students-sensitive.csv': rows,
            'data/students.csv': rows,
        })
        code, out = _run(root)

        s.ok('SN-10', 'the shipped rule covers a marker-named file at any depth, by glob',
             'students-sensitive.csv' in out and 'ignored' in out
             and 'EXPOSED    data' not in out.replace(os.sep, '/'),
             'name the file for what it holds and it is covered before it exists')

        s.ok('SN-11', 'a file without the marker is still EXPOSED, which is why the marker is '
                      'the rule and not a nicety',
             code == 1 and 'students.csv' in out and 'SENSITIVE RED' in out,
             'the ignore rule prevents; the guard is what catches the one nobody named')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_patterns, group_states, group_clean, group_shipped_rule)
