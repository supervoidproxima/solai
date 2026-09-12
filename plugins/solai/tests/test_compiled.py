# -*- coding: utf-8 -*-
"""A vault regenerating from its OWN declarations, and what happens to a hand edit.

Everything here exists because of one failure. `validate_cards.py` always read the vault's
compiled `_system/os/classes/*.toml`, so a vault that renamed a class was still VALIDATED
correctly; the emitters read the package archetype, so the same vault could never be
REGENERATED correctly. Its `CLAUDE.md` went on naming a class it had retired, and `CLAUDE.md`
itself said not to hand-edit the block but to edit the declaration - which lived with the
generator, in a directory the vault's own governance put out of scope. One real vault gave
up and wrote a hand-maintained section titled "Where the generated sections are wrong".

`CP-04` and `CP-05` are the pair that matters most: a declaration file appearing or
disappearing is how a vault SAYS a class was added or retired, so both are notes and neither
is an error. Refusing either would block exactly the evolution this was built to permit.

`CP-07` through `CP-09` cover the three fates of a hand-edited region. The middle one,
RECONCILED, is the one worth reading: a block whose content the declaration has since caught
up with gets its stamp corrected rather than staying dirty forever. That is NOT the act
`lib/stamp.py` forbids - rewriting a hash to silence a mismatch with unknown content - and
the distinction is the whole reason the rule is safe.

`CP-15` through `CP-21` are the upgrade path. `--from-package` re-imported the archetype
whole, which deleted any class the vault declared and the package did not - `deliverable` in
the vault that invented it, `platform` and `subject` in the counselor. CP-15 and CP-17 are
the two halves of the rule: vault-only is kept, declared-by-both goes to the package. CP-19
is the one that would otherwise rot quietly, because a merged manifest that does not list
what sits beside it reads as drift on the very next run and reorders every generated index.
"""
import os
import shutil
import tempfile

from lib import decl, engine, regions, stamp

EXPECTED = 21
NAME = 'compiled'

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MANIFEST = '''\
schema    = 1
archetype = "fixture"
title     = "Fixture"
summary   = "A fixture archetype."

classes = ["alpha"]
lookups = []

[interview]
asks = ["mode", "root"]

[interview.defaults]
governance_tier = "light"

[ids]
card = "^[A-Z]{3}-[0-9]{3}$"
date = "YYYY-MM-DD"

[[folders]]
path = "cards"
purpose = "the cards"
[[folders]]
path = "_system/os"
purpose = "engine state"

[[artefacts]]
id      = "bond"
path    = "_system/os/vault.md"
mode    = "generated"
emitter = "bond"

[[loop]]
n = 1
name = "write a card"
skill = "/alpha"
out = "cards/"
'''

CLASS = '''\
schema = 1
class     = "alpha"
prefix    = "ALP"
folder    = "cards/alpha"
skill     = "alpha"
title     = "Alpha"
purpose   = "A fixture class."

[status]
lifecycle = ["open"]
terminal  = ["closed"]
default   = "open"

[[fields]]
name     = "title"
type     = "scalar"
card     = "1"
required = true
'''


def _write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def _vault(tmp, manifest=MANIFEST, classes=None, lookups=()):
    """A throwaway vault carrying only its compiled declarations."""
    root = tempfile.mkdtemp(prefix='solai-test-vault-', dir=tmp)
    os_dir = os.path.join(root, '_system', 'os')
    _write(os.path.join(os_dir, 'manifest.toml'), manifest)
    for name, text in (classes if classes is not None else {'alpha': CLASS}).items():
        _write(os.path.join(os_dir, 'classes', '%s.toml' % name), text)
    return root


def group_compiled(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-cp-')
    try:
        root = _vault(tmp)
        arch, notes = decl.load_compiled(root)
        s.ok('CP-01', 'a compiled manifest and its classes load without the package',
             arch.name == 'fixture' and [c.name for c in arch.classes] == ['alpha'],
             repr((arch.name, [c.name for c in arch.classes])))

        s.eq('CP-02', 'arch.root points at the vault, so source hashing keeps working',
             os.path.basename(arch.root), 'os')

        s.eq('CP-03', 'a clean compiled set reports no notes', notes, [])

        # A class file the manifest does not list. Adding the file IS the addition.
        root = _vault(tmp, classes={'alpha': CLASS,
                                    'beta': CLASS.replace('"alpha"', '"beta"')
                                                 .replace('"ALP"', '"BET"')
                                                 .replace('cards/alpha', 'cards/beta')})
        arch, notes = decl.load_compiled(root)
        s.ok('CP-04', 'a class compiled in but unlisted is a note and loads, not an error',
             len(arch.classes) == 2 and any('beta' in n and 'added' in n for n in notes),
             repr(notes))

        # A name the manifest lists with no file. Deleting the file IS the retirement.
        root = _vault(tmp, classes={})
        arch, notes = decl.load_compiled(root)
        s.ok('CP-05', 'a listed name with no declaration is a note reading as retired',
             arch.classes == [] and any('alpha' in n and 'retired' in n for n in notes),
             repr(notes))

        # The refusal a renamed vault meets on its first compiled run.
        root = _vault(tmp, classes={'alpha': CLASS.replace('cards/alpha', 'elsewhere')})
        s.raises('CP-06', 'a class folder under no declared folder is refused, and named',
                 lambda: decl.load_compiled(root), ('elsewhere', 'folder'),
                 exc=decl.DeclError)

        s.raises('CP-07', 'a vault with no compiled manifest says so rather than guessing',
                 lambda: decl.load_compiled(tempfile.mkdtemp(dir=tmp)),
                 'no compiled manifest', exc=decl.DeclError)

        # ---------------------------------------------------------------- hand edits
        src = 'a' * 16
        body = regions.insert('# Doc\n', 'demo', 'first', src, order=['demo'])
        edited = body.replace('first', 'second')

        new, verdicts = engine.merge_regions(edited, {'demo': 'third'}, src, ['demo'])
        s.eq('CP-08', 'a hand-edited region is left alone when the declaration disagrees',
             (verdicts['demo'], new == edited), (stamp.HAND_EDITED, True))

        new, verdicts = engine.merge_regions(edited, {'demo': 'second'}, src, ['demo'])
        s.eq('CP-09', 'a hand-edited region the declaration now produces is RECONCILED',
             verdicts['demo'], engine.RECONCILED)
        s.ok('CP-10', 'reconciling corrects the stamp and changes no visible content',
             regions.find_all(new)['demo'].content.strip() == 'second'
             and regions.find_all(new)['demo'].verdict(src) == stamp.CLEAN,
             repr(regions.find_all(new)['demo'].content))

        signed = {'demo': {'body-sha': stamp.body_sha(
            regions.find_all(edited)['demo'].content), 'because': 'CHG-042'}}
        new, verdicts = engine.merge_regions(edited, {'demo': 'third'}, src, ['demo'],
                                             adopted=signed)
        s.ok('CP-11', 'an adopted region reports its record and is still not overwritten',
             verdicts['demo'].startswith(engine.ADOPTED) and 'CHG-042' in verdicts['demo']
             and new == edited, repr(verdicts['demo']))

        stale_sig = {'demo': {'body-sha': 'not-the-one', 'because': 'CHG-042'}}
        new, verdicts = engine.merge_regions(edited, {'demo': 'third'}, src, ['demo'],
                                             adopted=stale_sig)
        s.eq('CP-12', 'adoption is void once the region is edited again',
             verdicts['demo'], stamp.HAND_EDITED)

        s.eq('CP-13', 'an empty adopted register is read as no adoptions, not as an error',
             engine.read_adopted(tempfile.mkdtemp(dir=tmp)), {})

        # A region nobody touched still costs nothing.
        new, verdicts = engine.merge_regions(body, {'demo': 'first'}, src, ['demo'])
        s.eq('CP-14', 'an untouched region is CLEAN and the file is unchanged',
             (verdicts['demo'], new == body), (stamp.CLEAN, True))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


PROJ = os.path.join(PKG_ROOT, 'archetypes', 'project', 'manifest.toml')
ZETA = (CLASS.replace('"alpha"', '"zeta"').replace('"ALP"', '"ZET"')
             .replace('"Alpha"', '"Zeta"').replace('cards/alpha', 'registry/zeta'))


def group_merge(s):
    """`--from-package` on a vault that declares a class the archetype does not carry."""
    tmp = tempfile.mkdtemp(prefix='solai-test-mg-')
    try:
        proj = decl._read_text(PROJ)
        gap = decl._read_text(os.path.join(PKG_ROOT, 'archetypes', 'project',
                                           'classes', 'gap.toml'))

        # A vault carrying one class of its own and nothing else. What the package declares
        # is not compiled in here, which is the shape of every real upgrade: the vault holds
        # judgement, the package holds the declarations it ships.
        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['zeta']),
                      classes={'zeta': ZETA})
        arch, notes = decl.load_merged(PKG_ROOT, root, 'project')
        names = [c.name for c in arch.classes]
        s.ok('CP-15', 'a class the vault declares alone survives the upgrade',
             'zeta' in names and 'gap' in names and arch.kept == ['zeta'], repr(names))

        s.ok('CP-16', 'the kept class is named in a note, so the plan says why the row is there',
             any('zeta' in n and 'Kept' in n for n in notes), repr(notes))

        s.ok('CP-17', 'a class declared by both resolves to the PACKAGE file',
             os.path.abspath(arch.classes[names.index('gap')].path).startswith(
                 os.path.abspath(os.path.join(PKG_ROOT, 'archetypes'))),
             arch.classes[names.index('gap')].path)

        # Byte-identical on both sides. Silence is the point: a note on every unchanged
        # class buries the one row that is actually being overwritten.
        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['gap', 'zeta']),
                      classes={'gap': gap, 'zeta': ZETA})
        arch, quiet = decl.load_merged(PKG_ROOT, root, 'project')
        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['gap', 'zeta']),
                      classes={'gap': gap.replace('schema = 1', 'schema = 1\n# edited here'),
                               'zeta': ZETA})
        arch2, loud = decl.load_merged(PKG_ROOT, root, 'project')
        s.ok('CP-18', 'an identical duplicate is silent and a differing one is reported',
             not any('gap' in n for n in quiet)
             and any('gap' in n and 'differ' in n for n in loud), repr((quiet, loud)))

        # The merged manifest, written back into a vault, must not read as drift.
        _write(os.path.join(root, '_system', 'os', 'manifest.toml'), arch2.manifest_text)
        for c in arch2.classes:
            _write(os.path.join(root, '_system', 'os', 'classes', '%s.toml' % c.name),
                   decl._read_text(c.path))
        back, back_notes = decl.load_compiled(root)
        s.ok('CP-19', 'the merged manifest lists the kept class, so the next run sees no drift',
             [c.name for c in back.classes] == [c.name for c in arch2.classes]
             and not any('zeta' in n for n in back_notes),
             repr(([c.name for c in back.classes], back_notes)))

        # A vault with nothing compiled in yet. Merging has nothing to merge WITH.
        bare = tempfile.mkdtemp(dir=tmp)
        arch3, none = decl.load_merged(PKG_ROOT, bare, 'project')
        s.eq('CP-20', 'a vault with no compiled manifest merges to the archetype whole',
             (arch3.kept, none, arch3.manifest_text), ([], [], None))

        s.raises('CP-21', 'a class list the merge cannot rewrite is refused, never guessed at',
                 lambda: decl._relist(proj.replace(
                     'classes = ["gap", "resolution", "pain", "proposal", "question"]',
                     'classes = [\n  "gap",\n]'), 'classes', ['gap']),
                 'single-line array', exc=decl.DeclError)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_compiled, group_merge)
