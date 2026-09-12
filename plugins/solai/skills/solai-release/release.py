# -*- coding: utf-8 -*-
"""Cut a release: gates LAST, then push, fast-forward, tag.

    py release.py            # check only. Writes nothing, pushes nothing.
    py release.py --apply    # do it, after every gate passes

WHY THIS EXISTS, and it is not about saving keystrokes. On 2026-09-12 a release ran the three
gates, then bumped a version, then committed. The bump truncated `lib/__init__.py`, so the
package could not import, and the commit went in with three green gate results sitting above it.
Nothing lied: the gates were green when they ran, and then the tree changed.

SO THE ORDER IS THE FEATURE. Gates are the LAST thing before the push, never a step that happens
earlier and is remembered as done. A dirty tree is refused outright for the same reason: an
uncommitted change is a change the gates did not see.

WHAT IT REFUSES, each naming itself rather than exiting on a number:
  a dirty working tree            - the gates would be testing something else
  a tag that already exists       - a released version is immutable
  a version no CHANGELOG row claims - a release nobody wrote down
  a branch behind its target      - the merge is judgement, and conflicts are not automatable
  any red gate                    - obviously, and it prints which

WHAT IT DOES NOT DO. It does not merge, because a conflict is a decision. It does not write into
any vault, because a vault reads its own declarations and this package does not reach into one.
It prints the vault obligation instead: a deliverable card is owed a `sent-on`, and a release
that ships while the vault still reads `0 sent` has made the one number that matters wrong.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(HERE))              # .../plugins/solai
REPO = os.path.dirname(os.path.dirname(PKG))              # the git repository root

sys.path.insert(0, PKG)
from lib import VERSION                                             # noqa: E402

GATES = (('package', 'tests/run_tests.py', 'GREEN'),
         ('engine', 'tests/verify_engine.py', 'VERIFICATION GREEN'),
         ('install', 'tests/verify_install.py', 'INSTALL GATE GREEN'))

TARGET = 'main'


def git(*args, cwd=REPO):
    p = subprocess.run(['git'] + list(args), cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace').strip()


def gate(script):
    p = subprocess.run([sys.executable, script], cwd=PKG,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def changelog_claims(version):
    p = os.path.join(PKG, 'skills', 'solai', 'CHANGELOG.md')
    if not os.path.exists(p):
        return False
    with open(p, encoding='utf-8') as fh:
        return re.search(r'Version\s+%s\b' % re.escape(version), fh.read()) is not None


def preflight():
    """Everything that is true before a single gate runs. Cheap, and it fails fast."""
    problems, facts = [], []

    _, branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    facts.append(('branch', branch))
    facts.append(('version', VERSION))

    _, dirty = git('status', '--porcelain')
    n = len([x for x in dirty.splitlines() if x.strip()])
    facts.append(('uncommitted files', str(n)))
    if n:
        problems.append('%d uncommitted file(s). The gates would be testing a tree that is not '
                        'the one being released; this is exactly how a broken commit got three '
                        'green gates above it.' % n)

    tag = 'v%s' % VERSION
    rc, _ = git('rev-parse', '-q', '--verify', 'refs/tags/%s' % tag)
    facts.append(('tag', tag + (' (EXISTS)' if rc == 0 else ' (free)')))
    if rc == 0:
        problems.append('tag %s already exists. A released version is immutable: bump first.'
                        % tag)

    if not changelog_claims(VERSION):
        problems.append('no CHANGELOG row claims "Version %s". A release nobody wrote down is a '
                        'release nobody can read back.' % VERSION)

    git('fetch', '-q', 'origin')
    rc, behind = git('rev-list', '--count', '%s..origin/%s' % (branch, TARGET))
    rc2, ahead = git('rev-list', '--count', 'origin/%s..%s' % (TARGET, branch))
    if rc == 0 and rc2 == 0:
        facts.append(('vs origin/%s' % TARGET, '%s ahead, %s behind' % (ahead, behind)))
        if behind.isdigit() and int(behind) > 0:
            problems.append('%s commits on origin/%s are not on this branch. Merge them here '
                            'first and resolve by hand: a conflict is a decision, and this '
                            'script does not make it.' % (behind, TARGET))
        if ahead.isdigit() and int(ahead) == 0:
            problems.append('nothing to release: this branch is not ahead of origin/%s.' % TARGET)
    return problems, facts


def main():
    apply_it = '--apply' in sys.argv[1:]
    print('solai release   %s' % VERSION)
    print('  repo %s' % REPO)
    print()

    problems, facts = preflight()
    for k, v in facts:
        print('  %-18s %s' % (k, v))
    print()

    if problems:
        print('refused:')
        for p in problems:
            print('  %s' % p)
        return 1

    # Gates LAST. Everything above is a property of the tree; this is a property of the code,
    # and it is measured at the last possible moment before anything leaves.
    print('gates, run now rather than earlier:')
    red = []
    for name, script, want in GATES:
        rc, out = gate(script)
        ok = rc == 0 and want in out
        print('  %-9s %s' % (name, 'green' if ok else 'RED'))
        if not ok:
            red.append((name, out.strip().splitlines()[-12:]))
    print()
    if red:
        print('refused: a gate is red.')
        for name, tail in red:
            print('\n  --- %s ---' % name)
            for line in tail:
                print('  %s' % line)
        return 1

    _, branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    tag = 'v%s' % VERSION
    if not apply_it:
        print('would do, in this order:')
        print('  git push origin %s' % branch)
        print('  git push origin %s:%s' % (branch, TARGET))
        print('  git tag -a %s && git push origin %s' % (tag, tag))
        print('\ncheck only. Nothing pushed. Re-run with --apply.')
        return 0

    for args in (('push', 'origin', branch),
                 ('push', 'origin', '%s:%s' % (branch, TARGET))):
        rc, out = git(*args)
        print('  git %s -> %s' % (' '.join(args), 'ok' if rc == 0 else out))
        if rc != 0:
            print('\nstopped. Nothing further was attempted.')
            return 1
    rc, out = git('tag', '-a', tag, '-m', 'solai %s' % VERSION)
    if rc != 0:
        print('  tag failed: %s' % out)
        return 1
    rc, out = git('push', 'origin', tag)
    print('  tag %s -> %s' % (tag, 'ok' if rc == 0 else out))
    if rc != 0:
        return 1

    print()
    print('released %s.' % tag)
    print()
    print('NOT DONE YET, and this script cannot do it for you.')
    print('  A deliverable card is owed `sent-on` and `status: sent`, and the change record')
    print('  that says what left. A release that ships while the vault still reads `0 sent`')
    print('  has made the one number the whole ratio is measured against wrong, and no amount')
    print('  of green gates here says anything about that.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
