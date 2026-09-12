# -*- coding: utf-8 -*-
"""Claim the next change number atomically, by creating the file, before writing a word in it.

WHY THIS EXISTS. Three times in ten days, in one vault, two writers read the same highest change
number and each wrote over the other's record. `CHG-118` there diagnosed it correctly and
prescribed the fix: claim the number by reading the folder immediately before the write. That
prescription lived in prose. Thirty records later `CHG-148` reports the same collision again, and
a fourth was found on a sync-conflicted branch on 2026-09-12.

WHY PROSE COULD NEVER HAVE FIXED IT. The failure is not a person choosing to reuse a number. It
is two writers reading the same maximum, and no instruction to "read immediately before writing"
removes the window between the read and the write - it only makes it shorter. The window has to
be closed by the operating system, not by discipline.

SO THE CLAIM IS THE CREATE. `os.open` with `O_CREAT | O_EXCL` either creates the file or fails
because someone else already did. There is no interval between checking and claiming, because
they are one call. A second writer racing for the same number loses the call, takes the next one,
and both records survive.

A HOLE IS CHEAPER THAN A REUSE. Numbering always continues from the highest seen, never fills a
gap. `CHG-118` is explicit about why: a reclaimed number breaks every true citation pointing at
the record that already holds it, to repair one that could simply have taken the next.
"""
import io
import os
import re
import sys

# The shared argument reader, beside this file in `_system/scripts/`. Imported by path rather
# than by package, because these scripts are copied into a vault and run standalone.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _args                                                        # noqa: E402

USAGE = '''\
usage: mint_change.py <vault> [--title "..."] [--date YYYY-MM-DD]\n  which number is mine, claimed by creating the file'''


STUB = """---
id: {id}
date: {date}
type: change
title: "{title}"
tags: []
---
# {id} - {title}

<!-- This file was created to CLAIM {id}. It is a placeholder until the body is written, and
     a placeholder that stays this way is itself a finding. -->

| Change | Reason | Impact |
|---|---|---|
|  |  |  |

Change records are immutable once written. Correcting one means writing the next.
"""


def changes_folder(root):
    """What this vault calls its change folder, from its own answers, not from a guess."""
    ans = os.path.join(root, '_system', 'os', 'answers.toml')
    if os.path.exists(ans):
        m = re.search(r'(?m)^changes_folder\s*=\s*"([^"]+)"', io.open(ans, encoding='utf-8').read())
        if m:
            return m.group(1)
    return 'changes'


def highest(folder, prefix='CHG'):
    """The highest number on disk. Read by globbing filenames, never by counting them: a folder
    of 147 records with five retired numbers in it counts to 142 and collides on the next write.
    """
    if not os.path.isdir(folder):
        return 0
    rx = re.compile(r'^%s-(\d+)\.md$' % re.escape(prefix))
    best = 0
    for name in os.listdir(folder):
        m = rx.match(name)
        if m:
            best = max(best, int(m.group(1)))
    return best


def mint(root, title, date, prefix='CHG', width=3, limit=1000):
    """Create the next free record and return (id, path).

    The return value is a file that now EXISTS. Nothing here reserves a number in memory and
    hands it back to be written later: that gap is the defect.
    """
    folder = os.path.join(root, changes_folder(root))
    os.makedirs(folder, exist_ok=True)
    n = highest(folder, prefix)
    for _ in range(limit):
        n += 1
        cid = '%s-%0*d' % (prefix, width, n)
        path = os.path.join(folder, '%s.md' % cid)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            # Another writer holds it. Not an error, and not something to inspect: reading the
            # file to decide whether it "looks like a draft" is how one gets overwritten.
            continue
        except OSError:
            raise
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(STUB.format(id=cid, date=date, title=title))
        return cid, path
    raise RuntimeError('no free %s number in %d attempts from %s' % (prefix, limit, folder))


def main():
    root, opts, done = _args.parse(sys.argv[1:], USAGE, values=('--title', '--date'),
                                   default_root=None)
    if done:
        print(done[1])
        return done[0]
    title = opts['--title'] or 'Untitled'
    date = opts['--date']
    if not date:
        import datetime
        date = datetime.date.today().isoformat()

    cid, path = mint(root, title.replace('"', "'"), date)
    print('%s   %s' % (cid, os.path.relpath(path, root)))
    print('  claimed by creating the file. Write the body into it now; the number is yours.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
