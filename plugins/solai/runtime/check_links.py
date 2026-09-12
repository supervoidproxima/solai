# -*- coding: utf-8 -*-
"""Broken wikilinks, and what nothing points at.

    py _system/scripts/check_links.py <vault-root> [--orphans] [--json]

Obsidian resolves `[[name]]` by filename, not by path, so a link survives a folder move and
breaks on a rename. That asymmetry is why this runs after any structural change: the moves
are safe and the renames are not, and nothing else tells you which happened.

THE WORD "ORPHAN" IS NOT REPORTED HERE. It ran together two different facts - a note nothing
links to, and a note nothing can reach - and a `.base` view lists notes without wikilinking
them, so every note a view showed was being counted as unreachable. In one vault that made
383 orphans of which 326 were not orphans at all. A count that is 85% noise is a count
nobody acts on, so the small honest number is reported first and the reachable ones after.

Exit 1 on a broken link only. A note nothing points at is a fact about the graph, not a
failure: a freshly built vault is full of them and its checker should not be red.
"""
import io
import json
import os
import re
import sys

# The shared argument reader, beside this file in `_system/scripts/`. Imported by path rather
# than by package, because these scripts are copied into a vault and run standalone.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _args                                                        # noqa: E402

USAGE = '''\
usage: check_links.py [<vault>] [--json] [--orphans]
  is any wikilink broken, and what is reachable through nothing'''


sys.stdout.reconfigure(encoding='utf-8')

SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules', '__pycache__', '.claude'}
LINK = re.compile(r'\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]')
CODE_FENCE = re.compile(r'```.*?```', re.S)
INLINE_CODE = re.compile(r'`[^`\n]*`')
# `lib/emit/bases.py` writes exactly `- type == "duty"`. A filter this cannot parse simply
# does not answer the one question asked here - does a view list notes of this type - and
# no view is ever treated as making a note unreachable.
BASE_TYPE = re.compile(r'type\s*==\s*"([^"]+)"')
FM_TYPE = re.compile(r'(?m)^type:[ \t]*["\']?([A-Za-z0-9_-]+)')
HEAD = 8192
QUOTES = '"' + "'"
# Not attachments, so not reported as unreferenced ones. A note is counted separately, a
# `.base` IS the view rather than a thing a view should point at, and an `.html` here is a
# rendered projection of the vault: nothing should link to a dashboard, and reporting it
# every run is how a checker teaches people to skip its last line. Dotfiles are excluded
# for the same reason - repo plumbing is not an attachment anyone forgot to describe.
NOT_ATTACHMENTS = ('.md', '.base', '.html')


def _head(path):
    try:
        with io.open(path, encoding='utf-8') as fh:
            return fh.read(HEAD)
    except (OSError, UnicodeDecodeError):
        return ''


def aliases_of(text):
    """Every alias a note answers to.

    Obsidian resolves a wikilink against `aliases:` as well as against the filename, so an
    index built from filenames alone calls a working citation broken. Moving one class to
    slug filenames left 253 citations resolving through aliases and nothing else.

    Only the head of the file is read: frontmatter is at the top by definition.
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if not line.startswith('aliases:'):
            continue
        rest = line[len('aliases:'):].strip()
        if rest.startswith('[') and rest.endswith(']'):
            inner = rest[1:-1].strip()
            return [x.strip().strip(QUOTES) for x in inner.split(',') if x.strip()]
        out = []
        for nxt in lines[i + 1:]:
            if nxt.startswith((' ', '\t')):
                m = re.match(r'^\s*-\s+(.*?)\s*$', nxt)
                if m:
                    out.append(m.group(1).strip().strip(QUOTES))
            elif nxt.strip():
                break
        return out
    return []


def base_types(root):
    """Every note `type` that some `.base` view lists.

    A view is reachability. It is not a wikilink, so nothing in the link graph records it,
    and treating the notes it shows as unreachable is the mistake this exists to prevent.
    """
    types = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith('.base'):
                types.update(BASE_TYPE.findall(_head(os.path.join(dirpath, name))))
    return types


def index(root):
    """Every name a wikilink may resolve to, the files, and the head of each note."""
    by_name, all_files, heads = {}, [], {}
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
            # `[[folder/file.docx]]`: the relative path WITH its extension. Obsidian
            # accepts that form and writes it when linking to an attachment. Leaving
            # it out reported every citation to a PDF or DOCX as broken, which trains
            # people to ignore this checker.
            by_name.setdefault(rel, []).append(rel)
            if rel.endswith('.md'):
                heads[rel] = _head(path)
                for alias in aliases_of(heads[rel]):
                    by_name.setdefault(alias, []).append(rel)
    return by_name, all_files, heads


def scan(root):
    by_name, all_files, heads = index(root)
    views = base_types(root)
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

    no_inbound = [f for f in all_files
                  if f.endswith('.md') and f not in inbound
                  and not f.startswith('_system/') and f != 'CLAUDE.md']
    listed, unreachable = [], []
    for f in no_inbound:
        m = FM_TYPE.search(heads.get(f, ''))
        (listed if (m and m.group(1) in views) else unreachable).append(f)
    # The half `.md`-only scanning leaves out: a binary nothing points at is invisible to a
    # link check that reports only on notes, and a vault built on an archive is mostly
    # binaries. Whether one is DESCRIBED is a different question, asked by check_binaries.py.
    attachments = [f for f in all_files
                   if not f.endswith(NOT_ATTACHMENTS) and f not in inbound
                   and not f.startswith('_system/')
                   and not os.path.basename(f).startswith('.')]
    return {'broken': broken, 'no-inbound': no_inbound, 'listed-in-a-base': listed,
            'unreachable': unreachable, 'attachments-unreferenced': attachments,
            'files': len(all_files)}


def main():
    root, opts, done = _args.parse(sys.argv[1:], USAGE, flags=('--json', '--orphans'), values=())
    if done:
        print(done[1])
        return done[0]
    r = scan(root)
    broken = r['broken']
    if opts['--json']:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1 if broken else 0
    print('files %d   broken links %d   no inbound wikilink %d'
          % (r['files'], len(broken), len(r['no-inbound'])))
    print('  reachable through nothing       %d' % len(r['unreachable']))
    print('  listed in a base view           %d' % len(r['listed-in-a-base']))
    print('  attachments nothing points at   %d' % len(r['attachments-unreferenced']))
    for b in broken[:60]:
        print('  BROKEN  %s:%d  ->  [[%s]]' % (b['from'], b['line'], b['target']))
    if len(broken) > 60:
        print('  ... and %d more' % (len(broken) - 60))
    if opts['--orphans']:
        # The honest number first, in full. The rest are a backlog to read, not defects.
        for o in r['unreachable']:
            print('  UNREACHABLE  %s' % o)
        for o in r['listed-in-a-base'][:60]:
            print('  IN A VIEW    %s' % o)
        if len(r['listed-in-a-base']) > 60:
            print('  ... and %d more listed in a view' % (len(r['listed-in-a-base']) - 60))
        for o in r['attachments-unreferenced'][:60]:
            print('  ATTACHMENT   %s' % o)
        if len(r['attachments-unreferenced']) > 60:
            print('  ... and %d more attachments' % (len(r['attachments-unreferenced']) - 60))
    elif r['unreachable'] or r['attachments-unreferenced']:
        print('  (run with --orphans to list them)')
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
