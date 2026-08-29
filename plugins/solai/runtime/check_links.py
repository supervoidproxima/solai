# -*- coding: utf-8 -*-
"""Broken wikilinks and orphans.

    py _system/scripts/check_links.py <vault-root> [--orphans] [--json]

Obsidian resolves `[[name]]` by filename, not by path, so a link survives a folder move and
breaks on a rename. That asymmetry is why this runs after any structural change: the moves
are safe and the renames are not, and nothing else tells you which happened.

Ported from a working vault script. Exit 1 on any broken link.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules', '__pycache__', '.claude'}
LINK = re.compile(r'\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]')
CODE_FENCE = re.compile(r'```.*?```', re.S)
INLINE_CODE = re.compile(r'`[^`\n]*`')


def index(root):
    """filename stem (and full relative path) to real path."""
    by_name, all_files = {}, []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            all_files.append(rel)
            stem = os.path.splitext(name)[0]
            by_name.setdefault(stem, []).append(rel)
            by_name.setdefault(name, []).append(rel)
            by_name.setdefault(os.path.splitext(rel)[0], []).append(rel)
    return by_name, all_files


def scan(root):
    by_name, all_files = index(root)
    broken, inbound = [], {}
    for rel in all_files:
        if not rel.endswith('.md'):
            continue
        try:
            with io.open(os.path.join(root, rel.replace('/', os.sep)), encoding='utf-8') as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        # links inside code are examples, not references
        text = INLINE_CODE.sub('', CODE_FENCE.sub('', text))
        for n, line in enumerate(text.split('\n'), 1):
            for m in LINK.finditer(line):
                target = m.group(1).strip()
                if not target:
                    continue
                hits = by_name.get(target)
                if not hits:
                    broken.append({'from': rel, 'line': n, 'target': target})
                else:
                    for h in hits:
                        inbound[h] = inbound.get(h, 0) + 1
    orphans = [f for f in all_files
               if f.endswith('.md') and f not in inbound
               and not f.startswith('_system/') and f != 'CLAUDE.md']
    return broken, orphans, len(all_files)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = os.path.abspath(args[0]) if args else os.getcwd()
    broken, orphans, total = scan(root)
    if '--json' in sys.argv:
        print(json.dumps({'broken': broken, 'orphans': orphans, 'files': total},
                         ensure_ascii=False, indent=2))
        return 1 if broken else 0
    print('files %d   broken links %d   orphans %d' % (total, len(broken), len(orphans)))
    for b in broken[:60]:
        print('  BROKEN  %s:%d  ->  [[%s]]' % (b['from'], b['line'], b['target']))
    if len(broken) > 60:
        print('  ... and %d more' % (len(broken) - 60))
    if '--orphans' in sys.argv:
        for o in orphans[:60]:
            print('  ORPHAN  %s' % o)
        if len(orphans) > 60:
            print('  ... and %d more' % (len(orphans) - 60))
    elif orphans:
        print('  (%d orphans, run with --orphans to list them)' % len(orphans))
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
