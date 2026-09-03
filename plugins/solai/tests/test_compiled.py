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
"""
import os
import shutil
import tempfile

from lib import decl, engine, regions, stamp

EXPECTED = 14
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


GROUPS = (group_compiled,)
