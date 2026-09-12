# -*- coding: utf-8 -*-
"""Find personal identifiers in files that git would carry, before git carries them.

WHY THIS EXISTS, and it is not hypothetical. A vault built by this package held 728 children's
national identifiers in a file sitting untracked in the working tree. `git check-ignore` did not
claim it. A `git add` of its folder would have committed it, and a committed identifier cannot be
withdrawn. It was a sync client's conflict copy: the page it copied was ignored by a rule naming
that page exactly, and an exact name does not cover a copy of it.

THREE THINGS THAT FAILURE TEACHES, and this script is shaped by all three.

**Scan what nobody declared.** The generator's own check asked git about the page the generator
writes. Nothing asked about a file the generator never wrote, and a sync client writing a second
copy beside it is exactly that. So this walks the tree rather than a list.

**The dangerous state is not "tracked".** A tracked file carrying identifiers is a decision
someone made. An UNTRACKED file that no ignore rule covers is a decision nobody has made yet, and
it is one command from irreversible. That state is reported first and it is what turns the exit
code red.

**Never print what you found.** A guard that echoes the identifiers into a terminal, a CI log or
a run report has published them itself. Counts and paths only. There is no flag to change this.

WHAT IT CANNOT DO. It reads text. A spreadsheet, a PDF or a scan carrying the same identifiers is
counted as unscanned and listed as such, because a checker that silently skips binaries while
reporting green is claiming coverage it does not have.
"""
import os
import re
import subprocess
import sys

TEXT_EXT = {'.md', '.csv', '.txt', '.json', '.toml', '.yaml', '.yml', '.html', '.htm',
            '.base', '.tsv', '.xml', '.js', '.py', '.sql'}

SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.obsidian'}

# A pattern earns its place by being specific enough that a hit is worth a human look. `min_red`
# is how many distinct hits in one file make it a finding rather than a mention: one identifier
# in a worked example is documentation, forty is a register.
PATTERNS = (
    ('national-id-12',
     re.compile(r'(?<!\d)\d{12}(?!\d)'),
     3,
     'twelve consecutive digits. The Kazakhstan IIN and several other national identifiers '
     'take this shape'),
    ('email',
     re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
     10,
     'an address is personal data even when it is a work address'),
    ('iban',
     re.compile(r'(?<![A-Z0-9])[A-Z]{2}\d{2}[A-Z0-9]{11,30}(?![A-Z0-9])'),
     1,
     'a bank account number'),
    ('card-16',
     re.compile(r'(?<!\d)(?:\d[ -]?){15}\d(?!\d)'),
     1,
     'sixteen digits in card shape'),
)


def run(args, cwd):
    try:
        p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode('utf-8', 'replace')
    except (OSError, ValueError):
        return 1, ''


def git_state(root):
    """Which files git tracks, and which untracked ones no ignore rule covers.

    Returns (tracked, exposed, is_repo). `exposed` is the CHG-134 state: present, unignored,
    uncommitted. One `git add` from permanent.
    """
    rc, _ = run(['git', 'rev-parse', '--is-inside-work-tree'], root)
    if rc != 0:
        return set(), set(), False
    _, out = run(['git', 'ls-files'], root)
    tracked = {os.path.normpath(x) for x in out.splitlines() if x.strip()}
    # `--others` is untracked; without `--ignored` git omits anything a rule already covers, so
    # what comes back is precisely the set no rule claims.
    _, out2 = run(['git', 'ls-files', '--others', '--exclude-standard'], root)
    exposed = {os.path.normpath(x) for x in out2.splitlines() if x.strip()}
    return tracked, exposed, True


def scan_file(path):
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except OSError:
        return None
    if b'\x00' in raw[:4096]:
        return None
    text = raw.decode('utf-8', 'replace')
    found = {}
    for name, rx, _, _ in PATTERNS:
        hits = set(rx.findall(text))
        if hits:
            found[name] = len(hits)
    return found


def walk(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            yield os.path.join(base, f)


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
    tracked, exposed, is_repo = git_state(root)

    findings, unscanned = [], []
    for full in walk(root):
        rel = os.path.normpath(os.path.relpath(full, root))
        ext = os.path.splitext(full)[1].lower()
        if ext not in TEXT_EXT:
            unscanned.append(rel)
            continue
        found = scan_file(full)
        if found is None:
            unscanned.append(rel)
            continue
        if not found:
            continue
        if rel in exposed:
            state = 'EXPOSED'
        elif rel in tracked:
            state = 'TRACKED'
        else:
            state = 'ignored'
        findings.append((state, rel, found))

    red = [f for f in findings if f[0] == 'EXPOSED'
           and any(n >= dict((p[0], p[2]) for p in PATTERNS)[k] for k, n in f[2].items())]
    amber = [f for f in findings if f[0] == 'TRACKED']
    quiet = [f for f in findings if f[0] == 'ignored']

    print('check_sensitive   %s' % root)
    if not is_repo:
        print('  not a git repository: every finding below is reported as `ignored`, because '
              'there is nothing here that would carry it anywhere.')
    print()

    def line(state, rel, found):
        counts = ', '.join('%s x%d' % (k, v) for k, v in sorted(found.items()))
        print('  %-9s %-58s %s' % (state, rel[:58], counts))

    def show(rows, title, fold_over=12):
        # Folded above `fold_over`, because a list of six hundred rows is not read and a
        # checker nobody reads is a checker that is not running.
        print('%s: %d' % (title, len(rows)))
        if len(rows) <= fold_over:
            for state, rel, found in rows:
                line(state, rel, found)
            print()
            return
        folders = {}
        for state, rel, found in rows:
            d = os.path.dirname(rel) or '.'
            agg = folders.setdefault(d, [0, {}])
            agg[0] += 1
            for k, v in found.items():
                agg[1][k] = agg[1][k] + v if k in agg[1] else v
        for d in sorted(folders, key=lambda x: -folders[x][0]):
            n, counts = folders[d]
            print('  %-9s %-58s %d files, %s'
                  % ('', (d + os.sep)[:58], n,
                     ', '.join('%s x%d' % (k, v) for k, v in sorted(counts.items()))))
        print('  folded by folder. Re-run against one of them to see its files.')
        print()

    if red:
        print('RED. Untracked, unignored, and carrying identifiers. One `git add` from')
        print('permanent, and a committed identifier cannot be withdrawn.')
        show(red, '  files')
        print('  Fix the ignore rule with a GLOB, never an exact filename: a sync client writes')
        print('  `page-MACHINE.html` beside `page.html`, and a rule naming the second does not')
        print('  cover the first.')
        print()
    if amber:
        show(amber, 'TRACKED and carrying identifiers (a decision someone made; check it was made)')
    if quiet:
        show(quiet, 'carrying identifiers but ignored (no path to a commit from here)')

    print('not checked: %d files' % len(unscanned))
    print('  Binaries and non-text extensions are not read. A spreadsheet, a PDF or a scan')
    print('  carrying the same identifiers is in this number, not in the findings above.')
    print()
    print('scanned %d, findings %d, RED %d' % (
        sum(1 for _ in walk(root)) - len(unscanned), len(findings), len(red)))
    print('SENSITIVE %s' % ('RED' if red else 'GREEN'))
    return 1 if red else 0


if __name__ == '__main__':
    sys.exit(main())
