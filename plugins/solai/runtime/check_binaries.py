# -*- coding: utf-8 -*-
"""Is every binary described by a note, and is any described by two?

    py _system/scripts/check_binaries.py <vault-root> [--list] [--json]

A vault built on an archive is mostly not notes. `check_links.py` answers whether anything
POINTS AT a file; this answers whether anything SAYS WHAT IT IS. They are different
questions and only the second one survives the document being renamed, moved or forgotten.

Three ways a binary is described, in the order they are checked:

  same-stem   `report.pdf` beside `report.md`
  sidecar     a note whose `file:` names it, wherever that note lives
  folder      a note whose `folder:` covers the directory it sits in

CLAIMED BY TWO NOTES IS A DEFECT, and the only one here that exits non-zero. Two notes
describing one document will disagree eventually, and nothing in the vault says which to
read. Everything else is a printed backlog: a naming rule is a thing to work through, not a
build failure, and a checker that goes red on 300 legacy filenames is a checker nobody runs.

WHAT THIS DELIBERATELY DOES NOT DO. It does not judge whether a name is good prose. One
vault wrote that check, measured it at 326 hits almost all of them correct, and removed it
again. The transliteration word list such a check needs is specific to one vault's languages
and belongs under that vault's own governance, never in a package shipped to others.

Configurable, because "described" is a convention and not a fact. Defaults below; override
in `_system/os/attachments.toml`:

    [attachments]
    sidecar-key  = "file"
    folder-key   = "folder"
    max-basename = 60
    name-policy  = "ascii-kebab"    # the default is "any", which reports nothing on names
"""
import io
import json
import os
import re
import sys
import tomllib

# The shared argument reader, beside this file in `_system/scripts/`. Imported by path rather
# than by package, because these scripts are copied into a vault and run standalone.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _args                                                        # noqa: E402

USAGE = '''\
usage: check_binaries.py [<vault>] [--json] [--list]
  is every binary described by exactly one note'''


sys.stdout.reconfigure(encoding='utf-8')

SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules', '__pycache__', '.claude'}
# A note is not a binary, a `.base` IS the view, and an `.html` here is a rendered
# projection of the vault: nothing should describe a dashboard.
NOT_BINARIES = ('.md', '.base', '.html')
HEAD = 8192
WL = re.compile(r'\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]')
KEBAB = re.compile(r'^[a-z0-9]+(?:[-.][a-z0-9]+)*$')

# `name-policy` defaults to `any`, which reports nothing about names. The package cannot
# know what a good filename looks like in a vault it has never seen: one real vault names
# per-student documents `STU-2022-009-reference-letter.docx`, and an ascii-kebab rule flags
# 96 of its files for the capital letters its own convention requires. A naming rule is a
# vault's to declare, and this reports against it only once it has been.
DEFAULTS = {'sidecar-key': 'file', 'folder-key': 'folder',
            'max-basename': 60, 'name-policy': 'any'}


def config(root):
    p = os.path.join(root, '_system', 'os', 'attachments.toml')
    out = dict(DEFAULTS)
    if os.path.isfile(p):
        try:
            with open(p, 'rb') as fh:
                out.update(tomllib.load(fh).get('attachments', {}))
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return out


def _head(path):
    try:
        with io.open(path, encoding='utf-8') as fh:
            return fh.read(HEAD)
    except (OSError, UnicodeDecodeError):
        return ''


def fm_values(text, key):
    """Every value of one frontmatter key, inline list or block list or scalar."""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if not line.startswith(key + ':'):
            continue
        rest = line[len(key) + 1:].strip()
        if rest.startswith('[') and rest.endswith(']'):
            inner = rest[1:-1].strip()
            return [x.strip().strip('"' + "'") for x in inner.split(',') if x.strip()]
        if rest:
            return [rest.strip('"' + "'")]
        out = []
        for nxt in lines[i + 1:]:
            if nxt.startswith((' ', '\t')):
                m = re.match(r'^\s*-\s+(.*?)\s*$', nxt)
                if m:
                    out.append(m.group(1).strip().strip('"' + "'"))
            elif nxt.strip():
                break
        return out
    return []


def as_path(value):
    """A `file:` value is written as a quoted wikilink; take what it points at."""
    m = WL.search(value)
    return (m.group(1) if m else value).strip().replace(os.sep, '/')


def scan(root, cfg):
    binaries, notes = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, '/')
            if rel.startswith('_system/') or name.startswith('.'):
                continue
            if name.endswith(NOT_BINARIES):
                if name.endswith('.md'):
                    notes.append((rel, _head(os.path.join(dirpath, name))))
            else:
                binaries.append(rel)

    # Who claims what. A claim is recorded with the note that made it, because the report
    # that matters most is the one naming both notes that claimed the same document.
    claims = {}

    def claim(target, note, how):
        for b in binaries:
            hit = (b == target or os.path.basename(b) == target
                   or os.path.splitext(b)[0] == os.path.splitext(target)[0] and '/' not in target)
            if hit:
                claims.setdefault(b, []).append((note, how))
                return

    stems = {}
    for b in binaries:
        stems.setdefault(os.path.splitext(b)[0], []).append(b)
    covered_folders = {}
    for rel, head in notes:
        for v in fm_values(head, cfg['sidecar-key']):
            claim(as_path(v), rel, 'sidecar')
        for v in fm_values(head, cfg['folder-key']):
            covered_folders.setdefault(v.strip().strip('/'), []).append(rel)
        same = stems.get(os.path.splitext(rel)[0])
        for b in same or ():
            claims.setdefault(b, []).append((rel, 'same-stem'))

    for b in binaries:
        folder = b.rsplit('/', 1)[0] if '/' in b else ''
        for note in covered_folders.get(folder, ()):
            claims.setdefault(b, []).append((note, 'folder'))

    undescribed = [b for b in binaries if not claims.get(b)]
    # A folder note and a document's own note are not two claims on one document, they are
    # a set-level description and a document-level one, and a vault is meant to have both.
    # Only two SPECIFIC claims conflict: two notes each asserting they describe this file
    # will disagree eventually, and nothing says which to read.
    doubles = [(b, sorted({n for n, how in v if how != 'folder'}))
               for b, v in claims.items()
               if len({n for n, how in v if how != 'folder'}) > 1]
    tiers = {'sidecar': 0, 'same-stem': 0, 'folder only': 0}
    for b, v in claims.items():
        hows = {how for _, how in v}
        if 'sidecar' in hows:
            tiers['sidecar'] += 1
        elif 'same-stem' in hows:
            tiers['same-stem'] += 1
        else:
            tiers['folder only'] += 1
    over = [b for b in binaries
            if len(os.path.basename(b)) > int(cfg['max-basename'])]
    badly_named = []
    if cfg.get('name-policy') == 'ascii-kebab':
        badly_named = [b for b in binaries if not KEBAB.match(os.path.basename(b).lower())
                       or os.path.basename(b) != os.path.basename(b).lower()]
    return {'binaries': len(binaries), 'undescribed': sorted(undescribed),
            'claimed-twice': sorted(doubles), 'over-cap': sorted(over),
            'described-by': tiers, 'against-name-policy': sorted(badly_named)}


def main():
    root, opts, done = _args.parse(sys.argv[1:], USAGE, flags=('--json', '--list'), values=())
    if done:
        print(done[1])
        return done[0]
    cfg = config(root)
    r = scan(root, cfg)
    if opts['--json']:
        print(json.dumps({'config': cfg, **r}, ensure_ascii=False, indent=2))
        return 1 if r['claimed-twice'] else 0
    print('binaries %d   described by nothing %d   claimed twice %d'
          % (r['binaries'], len(r['undescribed']), len(r['claimed-twice'])))
    for tier, n in r['described-by'].items():
        print('  described by a %-14s %d' % (tier, n))
    print('  over the %d-character cap      %d'
          % (int(cfg['max-basename']), len(r['over-cap'])))
    if cfg.get('name-policy') != 'any':
        print('  against the name policy (%s)  %d'
              % (cfg.get('name-policy'), len(r['against-name-policy'])))
    for b, notes in r['claimed-twice'][:40]:
        print('  TWICE   %s  <-  %s' % (b, ', '.join(sorted(set(notes)))))
    if opts['--list']:
        for b in r['undescribed'][:80]:
            print('  UNDESCRIBED  %s' % b)
        if len(r['undescribed']) > 80:
            print('  ... and %d more' % (len(r['undescribed']) - 80))
        for b in r['over-cap'][:40]:
            print('  TOO LONG     %s' % b)
        for b in r['against-name-policy'][:40]:
            print('  NAME         %s' % b)
    elif r['undescribed'] or r['over-cap'] or r['against-name-policy']:
        print('  (run with --list to see them)')
    # Only the double claim is a failure. The rest is work to do, and work to do is not
    # a broken build.
    return 1 if r['claimed-twice'] else 0


if __name__ == '__main__':
    sys.exit(main())
