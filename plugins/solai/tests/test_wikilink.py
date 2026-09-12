# -*- coding: utf-8 -*-
"""12 assertions on the one wikilink pattern everything here shares.

WHAT THEY GUARD. `GAP-013`: Obsidian requires the alias separator to be written `\\|` inside a
table cell, five patterns in this package read a wikilink, and none of them allowed it. Every
link in every table read as broken. On one 1,769-file vault that was 1,808 reported defects
where there were 8, and the 8 real ones were invisible inside the noise.

`WL-08` is the one that keeps this true rather than merely making it true today: it reads every
file that parses a wikilink and demands the pattern come from the shared module. A sixth pattern
written by hand is how the first five happened.

`WL-02` to `WL-05` hold what the shipped pattern already got right. They pass against the
defective version too, and are kept for that reason: a fix that also changes what worked is not
a fix, and these are the assertions that would say so.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
RUNTIME = os.path.join(PKG, 'runtime')
sys.path.insert(0, RUNTIME)

import _wikilink                                                    # noqa: E402

EXPECTED = 12
NAME = 'wikilink'

# Every file that reads a wikilink, and what it reads one for.
READERS = {
    os.path.join(RUNTIME, 'check_links.py'): 'every link in the body',
    os.path.join(RUNTIME, 'check_binaries.py'): 'which document a sidecar claims',
    os.path.join(RUNTIME, 'validate_cards.py'): 'what a frontmatter value names',
    os.path.join(PKG, 'skills', 'solai-kb', 'kb_build.py'): 'the served text and the record',
    os.path.join(PKG, 'skills', 'solai-kb', 'kb_site.py'): 'the same, for the site',
}

ARCHETYPES = os.path.join(PKG, 'archetypes')

NOTE = '---\ntype: note\n---\n\n%s\n'


def found(text):
    return [(m.group(1), m.group(2)) for m in _wikilink.LINK.finditer(text)]


def run(args, cwd):
    p = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def group_pattern(s):
    cell = r'| [[subjects/SUB-028\|Physics]] | 5 |'
    s.ok('WL-01', 'the escaped pipe a table cell requires is the alias separator, not part '
                  'of the target',
         found(cell) == [('subjects/SUB-028', 'Physics')], repr(found(cell)))

    plain = '[[GAP-013|the gap]]'
    s.ok('WL-02', 'an unescaped alias, outside a table, reads exactly as it did before',
         found(plain) == [('GAP-013', 'the gap')], repr(found(plain)))

    bare = 'see [[GAP-013]] for it'
    s.ok('WL-03', 'a bare link is its target, and the alias is None rather than empty',
         found(bare) == [('GAP-013', None)], repr(found(bare)))

    anchors = r'[[note#^8b2357\|alias]] [[note#Heading]] [[note#^8b2357]]'
    s.ok('WL-04', 'an anchor is an address inside a note and never part of its name, '
                  'whether the alias after it is escaped or not',
         [t for t, _a in found(anchors)] == ['note', 'note', 'note'], repr(found(anchors)))

    mixed = r'[[a]] and [[b\|B]] and [[c|C]] and [[d/e\|E]]'
    s.ok('WL-05', 'escaped and unescaped links read the same on one line',
         [t for t, _a in found(mixed)] == ['a', 'b', 'c', 'd/e'], repr(found(mixed)))

    s.ok('WL-06', 'a frontmatter value written with the escape names the note, and a value '
                  'that is not a link names nothing',
         (_wikilink.target(r'"[[subjects/SUB-028\|Physics]]"'.strip('"')) == 'subjects/SUB-028'
          and _wikilink.target('[[GAP-013]]') == 'GAP-013'
          and _wikilink.target('not a link') is None),
         repr([_wikilink.target(r'[[subjects/SUB-028\|Physics]]'),
               _wikilink.target('[[GAP-013]]'), _wikilink.target('not a link')]))

    lst = [r'[[GAP-013\|the gap]]', '[[RES-013]]', 'ENG', '']
    s.ok('WL-07', 'a list value yields every target it names, and a bare name is kept as one',
         _wikilink.targets(lst) == ['GAP-013', 'RES-013', 'ENG'],
         repr(_wikilink.targets(lst)))


def group_wired(s):
    own = []
    for path, _why in sorted(READERS.items()):
        text = io.open(path, encoding='utf-8').read()
        # `EMBED_RE` is the one escaped `[[` left in place: an embed is a different question,
        # asked only to remove it from the served text, and it reads no target.
        hand = [ln for ln in text.split('\n') if r'\[\[' in ln and 'EMBED_RE' not in ln]
        if 'import _wikilink' not in text or hand:
            own.append(os.path.basename(path))
    s.ok('WL-08', 'every file that reads a wikilink takes the pattern from the shared module '
                  'and writes none of its own',
         not own, 'writes its own: %s' % ', '.join(own))

    missing = []
    for name in sorted(os.listdir(ARCHETYPES)):
        man = os.path.join(ARCHETYPES, name, 'manifest.toml')
        if not os.path.isfile(man):
            continue
        text = io.open(man, encoding='utf-8').read()
        if '_wikilink.py' not in text:
            missing.append(name)
    s.ok('WL-09', 'the module ships into every vault, beside the scripts that import it',
         not missing, 'not in the copied list: %s' % ', '.join(missing))

    tmp = tempfile.mkdtemp(prefix='solai-wl-')
    try:
        # The defect itself, in the shape it was met in: a vault whose links live in a table.
        io.open(os.path.join(tmp, 'index.md'), 'w', encoding='utf-8').write(
            NOTE % ('| subject | mark |\n|---|---|\n'
                    r'| [[note-b\|B]] | 5 |' + '\n'
                    r'| [[note-c\|C]] | 4 |' + '\n\nAlso [[note-b]] and [[note-c|C]].'))
        for stem in ('note-b', 'note-c'):
            io.open(os.path.join(tmp, stem + '.md'), 'w', encoding='utf-8').write(
                NOTE % 'back to [[index]]')
        code, out = run([os.path.join(RUNTIME, 'check_links.py'), tmp, '--json'], tmp)
        broken = json.loads(out)['broken'] if out.startswith('{') else ['unparsed: %s' % out[:120]]
        s.ok('WL-10', 'a vault whose links are written in a table reports no broken link, '
                      'where every one of them used to report broken',
             code == 0 and broken == [], repr((code, broken[:4])))

        att = os.path.join(tmp, 'attachments')
        os.makedirs(att)
        io.open(os.path.join(att, 'report-2026.pdf'), 'w', encoding='utf-8').write('x')
        io.open(os.path.join(tmp, 'the-report.md'), 'w', encoding='utf-8').write(
            '---\ntype: note\nfile: "[[attachments/report-2026.pdf\\|the report]]"\n---\n\nx\n')
        code, out = run([os.path.join(RUNTIME, 'check_binaries.py'), tmp, '--json'], tmp)
        r = json.loads(out) if out.startswith('{') else {}
        s.ok('WL-11', 'a sidecar claiming its document through an escaped pipe describes it, '
                      'where the document used to be described by nothing',
             r.get('undescribed') == [] and r.get('described-by', {}).get('sidecar') == 1,
             repr((code, r.get('undescribed'), r.get('described-by'))))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    sys.path.insert(0, os.path.join(PKG, 'skills', 'solai-kb'))
    import kb_build                                                 # noqa: E402
    served = kb_build.serve_text(r'Physics is [[subjects/SUB-028\|a subject]] here.')
    fields = kb_build.wikitargets([r'[[subjects/SUB-028\|Physics]]', '[[subjects/SUB-030]]'])
    s.ok('WL-12', 'the record a retrieval reads names the note its link field points at, and '
                  'the text served renders the alias rather than the path',
         served == 'Physics is a subject here.'
         and fields == ['subjects/SUB-028', 'subjects/SUB-030'],
         repr((served, fields)))


GROUPS = (group_pattern, group_wired)
