# -*- coding: utf-8 -*-
"""45 assertions on the four primitives: `fm`, `stamp`, `regions`, `fsplan`.

These are the four modules everything else in the package stands on, and three of the four
carry a guarantee that is invisible when it breaks:

  - `fm.patch` must not reformat a file it did not otherwise change, or every stamped file
    reads dirty forever and the user stops running the generator.
  - `stamp` must be blind to CRLF and trailing whitespace, because OneDrive, Obsidian and
    Windows all rewrite those without asking.
  - `stamp.strip_volatile` must drop a key AND its indented block, or the `.base` files read
    HAND-EDITED on the second run - the most visible artefact in the vault.
  - `regions` must find a MALFORMED marker, not only a well-formed one. A regex that matches
    only correct stamps makes a broken one invisible, which is worse than either alternative.

Counts: fm 14, stamp 11, regions 13, fsplan 7 (split across two groups, so a crash in
`apply` does not cost the plan-level assertions).
"""
import io
import json
import os
import shutil
import tempfile

from lib import fm, fsplan, regions, stamp

EXPECTED = 62
NAME = 'primitives'

VERSION = '0.4.0'


# --------------------------------------------------------------------------- fm

def group_fm(s):
    s.eq('FM-01', 'a file with no frontmatter yields (None, text)',
         fm.split('# Title\n\nbody\n'), (None, '# Title\n\nbody\n'))

    text = '---\ndate: 2026-08-27\ntype: note\n---\nBody line\n---\nnot frontmatter\n'
    fm_text, body = fm.split(text)
    s.ok('FM-02', 'split stops at the first standalone closing delimiter and join round-trips',
         fm_text == 'date: 2026-08-27\ntype: note'
         and body == 'Body line\n---\nnot frontmatter\n'
         and fm.join(fm_text, body) == text,
         'fm=%r body=%r' % (fm_text, body))

    s.eq('FM-03', 'an opening delimiter that is not alone on its line is not frontmatter',
         fm.split('--- note\na: 1\n---\nb\n')[0], None)

    meta = fm.parse('n: 12\nf: 1.5\nt: true\ny: yes\nfa: false\nnul: ~\nnone2: null\n'
                    'q: "a: b"\ns: plain text')
    s.ok('FM-04', 'scalars: int, float, bool, yes/no, null, and a quoted value keeps its colon',
         meta == {'n': 12, 'f': 1.5, 't': True, 'y': True, 'fa': False, 'nul': None,
                  'none2': None, 'q': 'a: b', 's': 'plain text'}, repr(meta))

    meta = fm.parse('e: []\nd: {}')
    s.ok('FM-05', 'an empty inline list is [] and an empty flow map is {}',
         meta == {'e': [], 'd': {}}, repr(meta))

    s.eq('FM-06', 'an inline list respects a comma inside a quoted item',
         fm.parse('t: ["a, b", c]')['t'], ['a, b', 'c'])

    s.eq('FM-07', 'a block list parses, quoted items unquoted',
         fm.parse('tags:\n  - one\n  - "two"')['tags'], ['one', 'two'])

    meta = fm.parse('a: 1\nempty:\nb: 2')
    s.ok('FM-08', 'a key with nothing under it is None, not an empty list',
         meta['empty'] is None and meta['a'] == 1 and meta['b'] == 2, repr(meta))

    s.eq('FM-09', 'a nested mapping parses one level down',
         fm.parse('permissions:\n  read: true\n  write: false')['permissions'],
         {'read': True, 'write': False})

    meta = fm.parse('# a standalone comment\na: 1 # trailing comment\nb: # only a comment')
    s.ok('FM-10', 'comment lines yield no key and a trailing comment is stripped from a value',
         meta == {'a': 1, 'b': None}, repr(meta))

    original = 'date: 2026-08-27\n# why this file exists\ntags: []\ntype: note'
    patched = fm.patch(original, {'tags': ['x', 'y']})
    s.eq('FM-11', 'patch replaces a key in place, preserving comments, order and the other keys',
         patched,
         'date: 2026-08-27\n# why this file exists\ntags:\n  - x\n  - y\ntype: note')

    s.eq('FM-12', 'patch appends a key that was missing',
         fm.patch('date: 2026-08-27', {'status': 'open'}),
         'date: 2026-08-27\nstatus: open')

    s.eq('FM-13', 'patch puts a newly added prepend key at the top, not the bottom',
         fm.patch('a: 1', {'type': 'note'}, prepend=('type',)),
         'type: note\na: 1')

    s.ok('FM-14', 'a wikilink value is quoted, and get() treats an unparsed key as absent',
         fm.patch('', {'link': '[[SYS-001]]'}) == 'link: "[[SYS-001]]"'
         and fm.get({'__unparsed__': ['x'], 'x': 1}, 'x', 'D') == 'D'
         and fm.get({}, 'y', 'D') == 'D',
         repr(fm.patch('', {'link': '[[SYS-001]]'})))


# --------------------------------------------------------------------------- stamp

def group_stamp(s):
    s.eq('ST-01', 'normalise: CRLF to LF, no trailing whitespace, exactly one final newline',
         stamp.normalise('a  \r\nb\t\r\n\r\n\r\n'), 'a\nb\n')

    base = 'line one\nline two\n'
    s.ok('ST-02', 'the hash is blind to CRLF, to a bare CR and to trailing whitespace',
         stamp.sha(base) == stamp.sha('line one  \r\nline two\r\n\r\n')
         == stamp.sha('line one\rline two\r')
         == stamp.sha('line one\nline two'),
         'OneDrive and Obsidian both rewrite these without asking. The bare-CR case is here '
         'because `rstrip` alone silently covers a trailing CR, so a CRLF assertion without it '
         'passes even when the line-ending normalisation is gone')

    volatile_text = ('views:\n'
                     '  - type: table\n'
                     '    name: All\n'
                     '    columnSize:\n'
                     '      note.id: 260\n'
                     '      note.status: 120\n'
                     '    order:\n'
                     '      - id\n')
    out = stamp.strip_volatile(volatile_text, ['columnSize'])
    s.ok('ST-03', 'strip_volatile drops the key AND its indented block, keeping the next sibling',
         'columnSize' not in out and 'note.id' not in out
         and 'order:' in out and 'name: All' in out, repr(out))

    s.eq('ST-04', 'strip_volatile with no patterns returns the text untouched',
         stamp.strip_volatile(volatile_text, None), volatile_text)

    s.eq('ST-05', 'source_sha is order-independent over its inputs',
         stamp.source_sha(VERSION, 'classes', [('a', '1'), ('b', '2')]),
         stamp.source_sha(VERSION, 'classes', [('b', '2'), ('a', '1')]))

    s.ok('ST-06', 'source_sha changes when the package version changes',
         stamp.source_sha(VERSION, 'classes', [('a', '1')])
         != stamp.source_sha('0.5.0', 'classes', [('a', '1')]),
         'a version bump must make every generated file read STALE')

    src = stamp.source_sha(VERSION, 'classes', [('claim.toml', 'abc')])
    body = '# Title\n\nSome generated body.\n'
    text = stamp.stamped_text('date: 2026-08-27\ntype: artefact', body, src, 'place %s' % VERSION)

    s.eq('ST-07', 'an unstamped file reads UNSTAMPED, never CLEAN',
         stamp.verdict('---\ndate: 2026-08-27\n---\nbody\n', src), stamp.UNSTAMPED)

    s.eq('ST-08', 'stamped_text output reads CLEAN against the source sha it was written with',
         stamp.verdict(text, src), stamp.CLEAN)

    s.eq('ST-09', 'a body edited after stamping reads HAND-EDITED',
         stamp.verdict(text + 'a human wrote this\n', src), stamp.HAND_EDITED)

    s.eq('ST-10', 'an intact body whose source moved reads STALE, which is safe to regenerate',
         stamp.verdict(text, 'deadbeefdeadbeef'), stamp.STALE)

    vol = ['columnSize']
    base_text = stamp.stamped_text('type: base', body, src, 'place %s' % VERSION, vol)
    polluted = base_text.replace('Some generated body.',
                                 'Some generated body.\ncolumnSize:\n  note.id: 260')
    s.eq('ST-11', 'a columnSize block injected by Obsidian still reads CLEAN',
         stamp.verdict(polluted, src, vol), stamp.CLEAN)


# --------------------------------------------------------------------------- regions

def group_regions(s):
    block = regions.render('card-index', 'one\ntwo', 'aaaa1111')
    text = 'Hand-written prose above.\n\n%s\n\nAnd prose below.\n' % block

    found = regions.find_all(text)
    reg = found.get('card-index')
    s.ok('RG-01', 'find_all parses the id, the src stamp and the region content',
         reg is not None and reg.src == 'aaaa1111' and reg.content == 'one\ntwo',
         repr(found))

    s.eq('RG-02', 'a begin marker with no matching end is skipped, never guessed at',
         regions.find_all('<!-- solai:begin foo src=a body=b -->\nx\n'), {})

    malformed = ('<!-- solai:begin foo src=?? body=?? -->\ncontent\n'
                 '<!-- solai:end foo -->\n')
    mreg = regions.find_all(malformed).get('foo')
    s.ok('RG-03', 'a malformed stamp is still FOUND, so it can be reported as malformed',
         mreg is not None and mreg.verdict('??') == stamp.HAND_EDITED, repr(mreg))

    yaml_block = regions.render('keys', 'a: 1', 'bbbb2222', comment='# ')
    yreg = regions.find_all('---\ntype: note\n%s\n---\nbody\n' % yaml_block).get('keys')
    s.ok('RG-04', 'a marker commented for YAML (leading #) is found inside a frontmatter block',
         yreg is not None and yreg.content == 'a: 1', repr(yaml_block))

    s.eq('RG-05', 'a freshly rendered region reads CLEAN against its own src',
         reg.verdict('aaaa1111'), stamp.CLEAN)

    s.eq('RG-06', 'a region whose src moved reads STALE',
         reg.verdict('cccc3333'), stamp.STALE)

    edited = regions.find_all(text.replace('one\ntwo', 'one\ntwo\nthree')).get('card-index')
    s.eq('RG-07', 'a region whose content was edited reads HAND-EDITED',
         edited.verdict('aaaa1111'), stamp.HAND_EDITED)

    def replace_absent():
        regions.replace(text, 'not-there', 'x', 'aaaa1111')
    s.raises('RG-08', 'replace refuses an absent region rather than inserting blindly',
             replace_absent, exc=KeyError)

    replaced = regions.replace(text, 'card-index', 'fresh', 'dddd4444')
    s.ok('RG-09', 'replace rewrites the region in place and leaves the prose either side',
         'fresh' in replaced and 'one\ntwo' not in replaced
         and replaced.startswith('Hand-written prose above.')
         and replaced.endswith('And prose below.\n'), repr(replaced))

    order = ('header', 'card-index', 'loop')
    two = ('%s\n\n%s\n' % (regions.render('header', 'H', 'h1'),
                           regions.render('loop', 'L', 'l1')))
    inserted = regions.insert(two, 'card-index', 'C', 'c1', order)
    pos = regions.find_all(inserted)
    s.ok('RG-10', 'insert honours the declared order, landing after the region that precedes it',
         pos['header'].start < pos['card-index'].start < pos['loop'].start, repr(inserted))

    only_last = regions.render('loop', 'L', 'l1') + '\n'
    inserted = regions.insert(only_last, 'card-index', 'C', 'c1', order)
    pos = regions.find_all(inserted)
    s.ok('RG-11', 'with no preceding region present, insert lands before the following one',
         pos['card-index'].start < pos['loop'].start, repr(inserted))

    plain = regions.insert('Just prose.\n', 'card-index', 'C', 'c1')
    # The second half is the twice-apply guarantee at its smallest: insert must be idempotent,
    # or the second run of an emitter appends a duplicate region instead of reading NOOP.
    again = regions.insert(plain, 'card-index', 'C', 'c1')
    s.ok('RG-12', 'with no declared order insert appends at the end, and re-inserting an '
                  'existing region replaces it rather than duplicating it',
         plain.startswith('Just prose.') and 'card-index' in regions.find_all(plain)
         and again.count('solai:begin card-index') == 1 and again == plain,
         repr(again))

    stripped = regions.strip_markers(text)
    s.ok('RG-13', 'strip_markers removes both markers and keeps the content',
         'solai:begin' not in stripped and 'solai:end' not in stripped
         and 'one\ntwo' in stripped, repr(stripped))


# --------------------------------------------------------------------------- fsplan

def group_fsplan_plan(s):
    root = tempfile.mkdtemp(prefix='solai-test-fs-')
    try:
        long_path = os.path.join(root, 'x.md')
        wrapped = fsplan.w(long_path)
        s.ok('FS-01', 'every path is wrapped for the Windows long-path limit',
             wrapped.startswith('\\\\?\\') if os.name == 'nt' else os.path.isabs(wrapped),
             wrapped)

        noop_only = fsplan.Plan(root, VERSION)
        noop_only.noop('a.md', 'card')
        mixed = fsplan.Plan(root, VERSION)
        mixed.write('new.md', 'card', 'fresh content\n', src='s1')
        mixed.noop('untouched.md', 'card')
        mixed.skip('edited.md', 'card', stamp.HAND_EDITED, 'hand-edited')
        mixed.skip('stale.md', 'card', stamp.STALE, 'stale')
        s.ok('FS-02', 'is_noop is true only when every action is a NOOP, and counts tally',
             noop_only.is_noop() and not mixed.is_noop()
             and mixed.counts == {'WRITE': 1, 'NOOP': 1, 'SKIP': 2}, repr(mixed.counts))

        blockers = mixed.blockers()
        s.ok('FS-03', 'blockers surfaces only the HAND-EDITED skips, not the stale ones',
             len(blockers) == 1 and blockers[0].rel == 'edited.md',
             repr([b.rel for b in blockers]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def group_fsplan_apply(s):
    """Separate group: a mutation that makes `apply` raise must not cost the plan assertions."""
    root = tempfile.mkdtemp(prefix='solai-test-fs-')
    try:
        # a file that already exists, so the pre-image and the backup path both get exercised
        existing = os.path.join(root, 'existing.md')
        with io.open(existing, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('original content\n')
        source = os.path.join(root, 'source-of-copy.py')
        with io.open(source, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('print("copied")\n')

        plan = fsplan.Plan(root, VERSION)
        plan.mkdir('folder/deeper')
        plan.mkdir('folder/deeper')          # the same folder, asked for twice
        plan.write('new.md', 'card', 'fresh content\n', src='s1')
        plan.write('existing.md', 'card', 'rewritten content\n', src='s2')
        plan.copy('_system/scripts/source-of-copy.py', 'scripts', source)
        plan.noop('never-written.md', 'card')
        plan.skip('also-never.md', 'card', stamp.HAND_EDITED, 'hand-edited')

        backup = os.path.join(root, '_backup')
        manifest_path = os.path.join(root, '_system', 'os', 'last-apply.json')
        # An apply that raises is itself the failure FS-04 is about: a SKIP carries no content,
        # so an engine that stops skipping them dies here rather than on the assertion below.
        # Catching it keeps the failure attributable to an id instead of a bare traceback.
        try:
            fsplan.apply(plan, manifest_path, backup)
            apply_error = None
        except Exception as err:                                    # noqa: BLE001
            apply_error = err

        s.ok('FS-04', 'apply writes the WRITE actions and writes nothing for NOOP or SKIP',
             apply_error is None
             and fsplan.read(os.path.join(root, 'new.md')) == 'fresh content\n'
             and fsplan.read(os.path.join(root, 'existing.md')) == 'rewritten content\n'
             and not fsplan.exists(os.path.join(root, 'never-written.md'))
             and not fsplan.exists(os.path.join(root, 'also-never.md')),
             'apply raised %r. A SKIP that writes is the whole failure mode this '
             'engine exists to prevent' % (apply_error,))

        residue = [f for f in os.listdir(root) if f.endswith('.solai-tmp')]
        s.eq('FS-08', 'one folder is one MKDIR row however many callers ask for it',
             len([a for a in plan.actions
                  if a.kind == fsplan.MKDIR and a.rel == 'folder/deeper']), 1)

        s.ok('FS-05', 'mkdir and copy land, and no temp sibling survives the atomic write',
             os.path.isdir(os.path.join(root, 'folder', 'deeper'))
             and fsplan.read(os.path.join(root, '_system', 'scripts', 'source-of-copy.py'))
             == 'print("copied")\n' and not residue, repr(residue))

        recorded = json.loads(fsplan.read(manifest_path))
        pre = {a['path']: a['pre'] for a in recorded['actions']}
        s.ok('FS-06', 'the manifest records a pre-image per write: existed, sha and mtime',
             len(recorded['actions']) == 3
             and pre['new.md']['existed'] is False
             and pre['existing.md']['existed'] is True
             and pre['existing.md']['sha'] and pre['existing.md']['mtime'] is not None
             and recorded['package_version'] == VERSION,
             'sha alone cannot tell a hand edit from a sync landing between plan and apply')

        result, err = fsplan.rollback(manifest_path)
        missing_result, missing_err = fsplan.rollback(os.path.join(root, 'no-such.json'))
        s.ok('FS-07', 'rollback deletes what did not exist, restores what did, '
                      'and refuses a missing manifest',
             err is None and result['removed'] == 2 and result['restored'] == 1
             and not fsplan.exists(os.path.join(root, 'new.md'))
             and fsplan.read(existing) == 'original content\n'
             and missing_result is None and 'no manifest' in (missing_err or ''),
             repr((result, err, missing_err)))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------- materials

def group_materials(s):
    """Documents handed to the engine at setup. The collector decides what gets copied, so a
    silent answer here is a file that never arrives or a file that overwrites another."""
    from lib import engine

    tmp = tempfile.mkdtemp(prefix='solai-test-mat-')
    try:
        src = os.path.join(tmp, 'src')
        os.makedirs(os.path.join(src, 'deep'))
        for rel in ('jd.md', 'deep/order.txt', 'deep/jd.md', '.hidden.md'):
            with io.open(os.path.join(src, rel.replace('/', os.sep)), 'w',
                         encoding='utf-8', newline='\n') as fh:
                fh.write('x ' + rel + '\n')
        binary = os.path.join(src, 'plan.pdf')
        with open(binary, 'wb') as fh:
            fh.write(b'%PDF-1.4\xff\xfe\x80 not decodable as utf-8')

        root = os.path.join(tmp, 'place')
        os.makedirs(root)

        files, errors = engine.collect_materials([src], root)
        s.eq('MAT-01', 'a folder is walked, its tree mirrored so a name repeated in a subfolder '
                       'arrives too, and a dotfile is not swept up with the rest',
             (sorted(rel for _, rel in files), errors),
             (['deep/jd.md', 'deep/order.txt', 'jd.md', 'plan.pdf'], []))

        files, errors = engine.collect_materials([os.path.join(tmp, 'nope')], root)
        s.ok('MAT-02', 'a path that is not there is refused by name and contributes no files',
             not files and len(errors) == 1 and 'no such path' in errors[0], repr(errors))

        twin = os.path.join(tmp, 'twin')
        os.makedirs(twin)
        with io.open(os.path.join(twin, 'jd.md'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('a different job description\n')
        files, errors = engine.collect_materials([src, twin], root)
        s.eq('MAT-03', 'one basename in two given folders is kept apart by the folder each came '
                       'from, and the names that do not clash are left alone',
             (sorted(rel for _, rel in files), errors),
             (['deep/jd.md', 'deep/order.txt', 'plan.pdf', 'src/jd.md', 'twin/jd.md'], []))

        for same in ('a', 'b'):
            os.makedirs(os.path.join(tmp, same, 'dup'))
            with io.open(os.path.join(tmp, same, 'dup', 'x.md'), 'w',
                         encoding='utf-8', newline='\n') as fh:
                fh.write('from ' + same + '\n')
        files, errors = engine.collect_materials(
            [os.path.join(tmp, 'a', 'dup'), os.path.join(tmp, 'b', 'dup')], root)
        s.ok('MAT-06', 'when the folder names cannot tell two files apart either, the refusal '
                       'says what to do instead of only that it happened',
             any('two files are called x.md' in e and 'one folder that holds both' in e
                 for e in errors), repr(errors))

        inside = os.path.join(root, 'sub')
        os.makedirs(inside)
        files, errors = engine.collect_materials([inside], root)
        s.ok('MAT-04', 'a path inside the vault itself is refused rather than copied into it',
             not files and any('inside the vault' in e for e in errors), repr(errors))

        s.ok('MAT-05', 'a binary hashes, which is what keeps the second plan NOOP',
             fsplan.bytes_sha(binary) is not None
             and stamp.file_sha(binary) is None
             and fsplan.bytes_sha(binary) == fsplan.bytes_sha(binary),
             'stamp.file_sha decodes utf-8 and answers None here; the copy check may not')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- language

def group_language(s):
    """What the place is written in, what its content is written in, and what a file NAME may
    carry. The last one decides a convention, so it is generated rather than seeded."""
    from lib.emit import claudemd as C

    s.eq('LG-01', 'one language arrives as a string and several as a list, and both read',
         (C.language_list({'content_languages': 'en|ru|kk'}, 'content_languages'),
          C.language_list({'content_languages': ['en', 'ru']}, 'content_languages')),
         (['en', 'ru', 'kk'], ['en', 'ru']))

    s.eq('LG-02', 'an unset content language falls back to what the place is written in',
         C.language_list({'output_language': 'ru'}, 'content_languages',
                         ('ru',)), ['ru'])

    got = C.naming(None, {'filename_language': 'content', 'content_languages': 'en|ru|kk'})
    s.ok('LG-03', 'the content policy names every language a file name may carry',
         'English, Russian and Kazakh' in got and 'Structure is named in English' in got,
         got[-400:])

    from lib import engine as E
    d = 'The list of what this role owes, handed to whoever appointed it.'
    s.eq('LG-05', 'a value equal to the type default is the type speaking, not a person',
         (E.promise_provenance(d, d), E.promise_provenance(' ' + d + ' ', d)),
         ('default', 'default'))
    s.eq('LG-06', 'anything else, and an empty answer, are labelled honestly',
         (E.promise_provenance('One list, by 30 September', d),
          E.promise_provenance('', d)), ('operator', 'default'))

    plain = C.naming(None, {'filename_language': 'english'})
    s.ok('LG-04', 'the English-only policy says so and offers frontmatter instead',
         'ASCII kebab whatever language' in plain and 'may be named in' not in plain,
         plain[-400:])


# --------------------------------------------------------------------------- start here

def group_starthere(s):
    """The file a person opens first. Every line of it is derived, so the assertions are about
    derivation: a hand-written paragraph per archetype is the thing this file exists to avoid."""
    import os
    from lib import decl
    from lib.emit import starthere

    pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    arch = decl.load_archetype(pkg, 'role')
    answers = {'name': 'SMP', 'remit': 'A remit.', 'package_version': '0.0.0',
               'first_artefact': arch.defaults.get('first_artefact'),
               'first_artefact_by': 'default'}
    got = starthere.render(None, arch, arch.classes, answers, '_inbox')

    s.ok('SH-01', 'session one is the first three steps of the declared loop, not prose',
         all(step['name'][:24] in got for step in arch.loop[:3])
         and arch.loop[3]['name'][:24] not in got,
         'the loop is the manifest\'s; the file only takes the top of it')

    s.ok('SH-02', 'the gate names the first class and the folder it writes to',
         arch.classes[0].name in got and arch.classes[0].folder in got, got[-600:])

    s.ok('SH-03', 'a promise nobody made is said out loud, and disappears once made',
         'Nobody has promised anything yet' in got
         and 'Nobody has promised anything yet' not in starthere.render(
             None, arch, arch.classes, dict(answers, first_artefact_by='operator'), '_inbox'),
         'the honesty line is the whole reason the default is tolerable')

    s.ok('SH-04', 'with no inbox declared, the inbox section is absent rather than empty',
         'First, the inbox' not in starthere.render(None, arch, arch.classes, answers, ''),
         'a heading with nothing under it teaches people to skip headings')


GROUPS = (group_fm, group_stamp, group_regions, group_fsplan_plan, group_fsplan_apply, group_materials, group_language, group_starthere)
