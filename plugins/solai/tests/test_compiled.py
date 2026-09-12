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

`CP-26` through `CP-29` are the case the first release of that loader missed: a vault with no
compiled manifest at all. It read a missing manifest as "nothing declared" and handed back the
package archetype whole, which is right for a first build and is a silent deletion for a vault
built before the manifest existed - the counselor, and every vault an upgrade is actually for.
CP-26 and CP-28 are the pair: declarations present with nothing recording them are kept, and an
`_system/os/` holding no declaration at all is still the archetype whole. The distinction is
between nothing declared and nothing RECORDED about what was declared, and a test that only
had one of them is what let the defect ship.

CP-28 passed before the fix as well, and is here for that reason rather than in spite of it:
it holds the case the fix must NOT change. Reverting the loader turns CP-26, CP-27 and CP-29
red and leaves CP-28 green, which is the shape a preservation assertion is supposed to have.

`CP-33` to `CP-36` are the other half of the merge: a class BOTH sides declare. The rule was
"the package wins", whole, and it cost a live vault the `filename = "slug"` it had decided on and
recorded, which turned nineteen cards invalid in the same second the upgrade landed. The package
is entitled to the engine's shape and not to what a vault's cards are called and shown by.

`CP-30` to `CP-32` are the folder a kept class lives in, and they exist because `zeta` above
sits at `registry/zeta`, under a folder `project` declares for its own reasons. Every assertion
on the merge passed on that coincidence, and so did the one real vault available, whose
`deliverable` lives in `deliverables/`. The counselor's classes live at `platforms/` and
`subjects/`, which no archetype declares, and the merge kept the class and then refused the set
it had just built. A fixture that shares an accidental property with the only live example
confirms whatever that property permits.

`CP-37` to `CP-42` are the branch for an artefact whose FORMAT can hold no stamp at all, which
is a different thing from a vault that has not been stamped yet. `registry.base` is bare YAML
and `START-HERE.md` has no frontmatter, so both read UNSTAMPED on every run of every vault and
the branch documented as a skip wrote over them anyway. The stamp moved beside the file, and the
state with no record splits by evidence rather than by assumption: identical to what would be
written is proof of authorship, and different is proof of nothing.

`CP-49` to `CP-53` are `RES-014`: a whole file can be signed for, the way a region already
could. The signature is over the bytes it was given for and it says what the package has
done since, so a vault that keeps its own copy stops being told, on every run forever, that
the engine cannot tell whose the file is.

`CP-50` passes with the feature reverted and is kept for that reason: a signature that survived
an edit to the file would be worse than no signature at all, and it is the assertion that would
say so.

`CP-43` to `CP-48` are the same argument for a file the package OWNS and the vault RUNS. That
branch had three fates and needed six, and the missing one was the ordinary one: the package
changed the file. Without a record of what was last copied in, "I changed this" and "you edited
this" are one observation, and it was resolved towards never writing. `CP-46` is the fate that did
not exist, and it is the reason a fix to a shipped script can be delivered at all.
"""
import io
import os
import shutil
import tempfile

from lib import decl, engine, fsplan, regions, stamp
from lib.emit import bases

EXPECTED = 54
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


def _vault(tmp, manifest=MANIFEST, classes=None, lookups=(), agents=(), workflows=()):
    """A throwaway vault carrying only its compiled declarations."""
    root = tempfile.mkdtemp(prefix='solai-test-vault-', dir=tmp)
    os_dir = os.path.join(root, '_system', 'os')
    _write(os.path.join(os_dir, 'manifest.toml'), manifest)
    for name, text in (classes if classes is not None else {'alpha': CLASS}).items():
        _write(os.path.join(os_dir, 'classes', '%s.toml' % name), text)
    for kind, given in (('agents', agents), ('workflows', workflows)):
        for name, text in dict(given).items():
            _write(os.path.join(os_dir, kind, '%s.toml' % name), text)
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

        # ------------------------------------------------- agents and workflows, same rule
        # A vault may declare an agent or a workflow of its own for the same reason it may
        # declare a class: `load_compiled` discovers all three by listing a directory. The
        # first release of this loader guarded classes alone and named the rest as uncovered,
        # which is an argument about today's vaults rather than about the rule.
        # Derived from what the package actually ships, renamed, rather than a second copy of
        # a fixture that would drift away from the loader it is meant to satisfy.
        proj_agent = decl._read_text(os.path.join(PKG_ROOT, 'common', 'agents', 'scout.toml'))
        proj_wf = decl._read_text(os.path.join(PKG_ROOT, 'common', 'workflows', 'review.toml'))
        mine_a = proj_agent.replace('agent = "scout"', 'agent = "probe"', 1)
        assert 'agent = "probe"' in mine_a, 'the scout fixture edit found nothing'
        mine_w = proj_wf.replace('workflow = "review"', 'workflow = "probe-job"', 1)

        root = _vault(tmp, manifest=decl._relist(
            decl._relist(decl._relist(proj, 'classes', []), 'agents', ['probe', 'scout']),
            'workflows', ['probe-job']),
            classes={}, agents={'probe': mine_a, 'scout': proj_agent},
            workflows={'probe-job': mine_w})
        arch, notes = decl.load_merged(PKG_ROOT, root, 'project')

        s.ok('CP-22', 'an agent the vault declares alone survives the upgrade and is named',
             'probe' in [a.name for a in arch.agents]
             and any("agents: 'probe'" in n and 'Kept' in n for n in notes),
             repr(([a.name for a in arch.agents], notes)))

        s.ok('CP-23', 'a workflow the vault declares alone survives the upgrade',
             'probe-job' in [w.name for w in arch.workflows]
             and any("workflows: 'probe-job'" in n and 'Kept' in n for n in notes),
             repr([w.name for w in arch.workflows]))

        s.ok('CP-24', 'an agent declared by both resolves to the PACKAGE file, silently',
             os.path.abspath(arch.agent('scout').path).startswith(
                 os.path.abspath(os.path.join(PKG_ROOT, 'common')))
             and not any("agents: 'scout'" in n for n in notes),
             repr((arch.agent('scout').path, notes)))

        s.ok('CP-25', 'the merged manifest names the kept agent and workflow, and the lists '
                      'that gained nothing are left exactly as the package wrote them',
             '"probe"' in arch.manifest_text and '"probe-job"' in arch.manifest_text
             and 'lookups = []' in arch.manifest_text
             and arch.manifest_text.count('classes = ["gap"') == 1,
             repr([l for l in arch.manifest_text.split('\n')
                   if l.startswith(('classes', 'lookups', 'agents', 'workflows'))]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_predates(s):
    """A vault older than the compiled manifest: declarations on disk, nothing listing them."""
    tmp = tempfile.mkdtemp(prefix='solai-test-pd-')
    try:
        agent = decl._read_text(os.path.join(PKG_ROOT, 'common', 'agents', 'scout.toml'))
        mine_a = agent.replace('agent = "scout"', 'agent = "probe"', 1)

        # The counselor's shape: `_system/os/classes/` holding a class of the vault's own,
        # and no `manifest.toml` anywhere, because the engine that built it compiled none.
        root = _vault(tmp, classes={'zeta': ZETA}, agents={'probe': mine_a})
        os.remove(os.path.join(root, '_system', 'os', 'manifest.toml'))
        arch, notes = decl.load_merged(PKG_ROOT, root, 'project')
        names = [c.name for c in arch.classes]

        s.ok('CP-26', 'a class the vault declares alone survives an upgrade with NO manifest',
             'zeta' in names and 'gap' in names and arch.kept == ['zeta', 'probe'],
             'the absence of a manifest says the vault is old, never that it declares '
             'nothing. Got %r kept %r' % (names, arch.kept))

        s.ok('CP-27', 'the kept class is named in a note, as it is when a manifest exists',
             any('zeta' in n and 'Kept' in n for n in notes), repr(notes))

        # Nothing declared, as against nothing recorded about what was declared. An
        # `_system/os/` a first build has just made, holding no declaration, is the first.
        empty = tempfile.mkdtemp(dir=tmp)
        os.makedirs(os.path.join(empty, '_system', 'os', 'classes'))
        fresh, none = decl.load_merged(PKG_ROOT, empty, 'project')
        s.eq('CP-28', 'an _system/os holding no declaration is still the archetype whole',
             (fresh.kept, none, fresh.manifest_text), ([], [], None))

        s.ok('CP-29', 'an agent declared alone survives it too, by the same rule',
             'probe' in [a.name for a in arch.agents]
             and any("agents: 'probe'" in n and 'Kept' in n for n in notes),
             repr([a.name for a in arch.agents]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_folders(s):
    """The folder a kept class lives in, which the package manifest never declared."""
    tmp = tempfile.mkdtemp(prefix='solai-test-fd-')
    try:
        proj = decl._read_text(PROJ)
        outside = ZETA.replace('registry/zeta', 'zetas')

        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['zeta']),
                      classes={'zeta': outside})

        # A refusal here is the defect, not a crash: without the carry, `_validate_set`
        # rejects the set the merge has just built. Caught so the assertion names it, because
        # a group that raises records one failure and loses every check after it.
        try:
            arch, notes = decl.load_merged(PKG_ROOT, root, 'project')
            refused = ''
        except decl.DeclError as err:
            arch, notes = None, []
            refused = ' | '.join(getattr(err, 'errors', ())) or str(err)

        paths = [f.get('path') for f in arch.folders] if arch else []
        s.ok('CP-30', 'a kept class carries the folder it lives in, and the note says why',
             'zetas' in paths
             and any('folders:' in n and 'zetas' in n and 'zeta' in n for n in notes),
             'keeping a declaration is not keeping what it needs. %s'
             % ('refused: %s' % refused if refused else 'got %r' % (paths,)))

        # Written back and re-read the way the next plain run reads it. A folder declared
        # only in memory is a folder the run after this one refuses the vault for.
        back, back_paths, back_names = None, [], []
        if arch is not None:
            _write(os.path.join(root, '_system', 'os', 'manifest.toml'), arch.manifest_text)
            for c in arch.classes:
                _write(os.path.join(root, '_system', 'os', 'classes', '%s.toml' % c.name),
                       decl._read_text(c.path))
            back, _ = decl.load_compiled(root)
            back_paths = [f.get('path') for f in back.folders]
            back_names = [c.name for c in back.classes]
        s.ok('CP-31', 'the merged manifest declares it, so the next plain run is not a refusal',
             'zetas' in back_paths and 'zeta' in back_names,
             'the merge never got that far' if back is None else repr(back_paths))

        # The case that must not change: a folder already covered is not declared twice.
        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['zeta']),
                      classes={'zeta': ZETA})
        covered, _ = decl.load_merged(PKG_ROOT, root, 'project')
        pkg_only, _ = decl.load_merged(PKG_ROOT, tempfile.mkdtemp(dir=tmp), 'project')
        s.eq('CP-32', 'a folder already covered by a declared one adds nothing',
             [f.get('path') for f in covered.folders],
             [f.get('path') for f in pkg_only.folders])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



def group_shared(s):
    """A class BOTH sides declare: which half of it the package is entitled to."""
    tmp = tempfile.mkdtemp(prefix='solai-test-sh-')
    try:
        proj = decl._read_text(PROJ)
        gap = decl._read_text(os.path.join(PKG_ROOT, 'archetypes', 'project',
                                           'classes', 'gap.toml'))
        # The counselor's shape: the package's own class, with the one key that decides what
        # its cards are CALLED changed, and a reason written above it. Losing this key made
        # nineteen cards invalid the moment an upgrade landed.
        # Both keys, because they travel together and the validator knows it: a slug
        # filename with no `id` column leaves the one view built for finding a card
        # unable to show its identifier. That pairing is why a vault editing one key
        # usually edits two, and why the residue in RES-009 is worth naming.
        mine = gap.replace('schema = 1',
                           'schema = 1\n\n# The filename is the slug: the graph view shows '
                           'filenames.\nfilename = "slug"', 1)
        mine = mine.replace('columns = ["file.name",', 'columns = ["file.name", "id",', 1)
        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['gap']),
                      classes={'gap': mine})
        arch, notes = decl.load_merged(PKG_ROOT, root, 'project')
        got = [c for c in arch.classes if c.name == 'gap'][0]

        s.ok('CP-33', 'a class differing only in what the vault owns resolves to the VAULT',
             os.path.abspath(got.path).startswith(os.path.abspath(root))
             and got.filename == 'slug',
             'an upgrade may not un-decide what a vault decided and wrote down. Got %s'
             % got.path)

        s.ok('CP-34', 'the note names the keys and says the vault keeps it',
             any("'gap'" in n and 'filename' in n and 'kept' in n for n in notes),
             repr(notes))

        # The same class, differing in a key the package owns as well. The package wins, and
        # what the vault loses is named rather than discovered later.
        both = mine.replace('prefix    = "GAP"', 'prefix    = "GAX"', 1)
        root = _vault(tmp, manifest=decl._relist(proj, 'classes', ['gap']),
                      classes={'gap': both})
        arch2, notes2 = decl.load_merged(PKG_ROOT, root, 'project')
        got2 = [c for c in arch2.classes if c.name == 'gap'][0]
        s.ok('CP-35', 'a class differing where the package owns goes to the PACKAGE, and the '
                      'note names both sets',
             os.path.abspath(got2.path).startswith(
                 os.path.abspath(os.path.join(PKG_ROOT, 'archetypes')))
             and any("'gap'" in n and 'prefix' in n and 'filename' in n for n in notes2),
             repr((got2.path, notes2)))

        # Agents have no vault-owned list, and nothing has needed one. The older rule stands,
        # stated here so its absence is a decision rather than an oversight.
        agent = decl._read_text(os.path.join(PKG_ROOT, 'common', 'agents', 'scout.toml'))
        root = _vault(tmp, manifest=decl._relist(decl._relist(proj, 'classes', []),
                                                 'agents', ['scout']),
                      classes={}, agents={'scout': agent + '\n# edited by the vault\n'})
        arch3, notes3 = decl.load_merged(PKG_ROOT, root, 'project')
        s.ok('CP-36', 'an agent declared by both still goes to the package, whole',
             os.path.abspath(arch3.agent('scout').path).startswith(
                 os.path.abspath(os.path.join(PKG_ROOT, 'common')))
             and any("'scout'" in n and 'overwritten' in n for n in notes3),
             repr(notes3))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



# --------------------------------------------------------- an artefact with nowhere to stamp

BASE_BODY = 'properties:\n  note.text:\n    displayName: description\nviews:\n'


def _one(tmp, name, body=None):
    """A vault root holding one unstampable artefact, or none at all."""
    root = os.path.join(tmp, name)
    os.makedirs(root)
    if body is not None:
        with io.open(os.path.join(root, 'registry.base'), 'w',
                     encoding='utf-8', newline='\n') as fh:
            fh.write(body)
    return root


def _plan_base(root, body=BASE_BODY, src='aaaaaaaaaaaaaaaa', force=(), stamps=None):
    plan = fsplan.Plan(root, '0.32.0')
    st = stamps if stamps is not None else engine.Stamps()
    engine._generated(plan, 'registry.base', 'registry-base', body, src, force,
                      volatile=bases.VOLATILE, fmeta=None, stamps=st)
    return plan.actions[0], st


def group_unstamped(s):
    """CP-37 to CP-42: the branch that used to write over anything it had not stamped.

    A `.base` carries no frontmatter and `START-HERE.md` carries none either, so both read
    UNSTAMPED on every run of every vault, including one written seconds before. The branch
    documented as `FOREIGN skip` fell through to `write`, and two Counselor applies replaced
    a hand-built base of nine views with the archetype's four. The stamps now live beside the
    artefact, and the state with no record splits by evidence: identical is proof it is ours,
    different is proof of nothing and is left alone.
    """
    tmp = tempfile.mkdtemp(prefix='solai-unstamped-')
    try:
        act, st = _plan_base(_one(tmp, 'absent', None))
        s.ok('CP-37', 'an absent unstampable artefact is written, and its stamp recorded',
             act.kind == fsplan.WRITE and 'registry.base' in st.next
             and st.next['registry.base'][stamp.KEY_BODY]
             == stamp.body_sha(stamp.normalise(BASE_BODY), bases.VOLATILE),
             repr((act.kind, st.next)))

        act, st = _plan_base(_one(tmp, 'identical', BASE_BODY))
        s.ok('CP-38', 'no record and byte-identical is adopted: NOOP, and the record written '
                      'down. The comparison has already proved what a flag would assert',
             act.kind == fsplan.NOOP and act.verdict == 'FOREIGN'
             and 'registry.base' in st.next, repr((act.kind, act.verdict, st.next)))

        act, st = _plan_base(_one(tmp, 'theirs', BASE_BODY + '  - type: table\n    name: nine\n'))
        s.ok('CP-39', 'no record and different is FOREIGN: skipped, not written, and not '
                      'claimed in the record either',
             act.kind == fsplan.SKIP and act.verdict == 'FOREIGN'
             and '--force registry-base' in act.reason and st.next == {},
             repr((act.kind, act.verdict, act.reason, st.next)))

        # The same file, now recorded, and then edited by somebody.
        rec = {'registry.base': stamp.record_for(stamp.normalise(BASE_BODY), 'aaaaaaaaaaaaaaaa',
                                                 'solai@0.32.0', bases.VOLATILE)}
        root = _one(tmp, 'edited', BASE_BODY + '  - type: table\n    name: mine\n')
        act, st = _plan_base(root, stamps=engine.Stamps(rec))
        s.ok('CP-40', 'a recorded artefact edited afterwards is HAND-EDITED, skipped, and its '
                      'old record kept: a file refused is a file not claimed',
             act.kind == fsplan.SKIP and act.verdict == stamp.HAND_EDITED
             and st.next == rec, repr((act.kind, act.verdict, st.next)))

        act, st = _plan_base(root, force=('registry-base',), stamps=engine.Stamps(rec))
        # The record must describe the bytes this action commits to write, never the bytes
        # that happened to be on disk. Rewriting a body-sha to silence a mismatch is the worst
        # single thing available here, and this is the assertion that would catch it.
        s.ok('CP-40b', '--force takes it, and the record describes what was actually written',
             act.kind == fsplan.WRITE
             and st.next['registry.base'][stamp.KEY_BODY]
             == stamp.body_sha(act.content, bases.VOLATILE),
             repr((act.kind, st.next)))

        act, st = _plan_base(_one(tmp, 'stale', BASE_BODY), src='bbbbbbbbbbbbbbbb',
                             stamps=engine.Stamps(rec))
        s.ok('CP-41', 'an intact recorded artefact whose source moved is STALE and regenerates',
             act.kind == fsplan.WRITE and act.verdict == stamp.STALE,
             repr((act.kind, act.verdict)))

        # The reason `strip_volatile` was written, finally reached. Before this the comparison
        # was byte-for-byte, so an apply discarded the column widths Obsidian itself wrote.
        opened = BASE_BODY + '    columnSize:\n      note.id: 260\n'
        act, st = _plan_base(_one(tmp, 'opened', opened), stamps=engine.Stamps(rec))
        s.ok('CP-42', 'a recorded base carrying the columnSize Obsidian wrote is NOOP, so an '
                      'apply no longer discards column widths',
             act.kind == fsplan.NOOP and st.next == rec,
             repr((act.kind, act.verdict, act.reason)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)




# ------------------------------------------------------- a file the package owns and we run

SHIPPED = '# a shipped script\nprint("one")\n'
MOVED = '# a shipped script\nprint("two")\n'


def _copied_case(tmp, name, here=None, shipped=SHIPPED, record=None, force=(), signed=None):
    """-> (action, stamps). A vault holding one copied file, or none, and a package source."""
    root = os.path.join(tmp, name)
    os.makedirs(os.path.join(root, 'vault', '_system', 'scripts'))
    src = os.path.join(root, 'src.py')
    with io.open(src, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(shipped)
    target = '_system/scripts/thing.py'
    if here is not None:
        with io.open(os.path.join(root, 'vault', '_system', 'scripts', 'thing.py'), 'w',
                     encoding='utf-8', newline='\n') as fh:
            fh.write(here)
    plan = fsplan.Plan(os.path.join(root, 'vault'), '0.34.0')
    st = engine.Stamps({target: record} if record else None)
    act = engine._copied(plan, target, 'scripts', src, force, st, signed)
    return act, st, target


def _sig(text, because='CHG-132', package_sha=None):
    """A signature over these bytes, optionally naming what the package shipped then."""
    row = {'body-sha': stamp.body_sha(text), 'because': because}
    if package_sha is not None:
        row['package-sha'] = package_sha
    return {'_system/scripts/thing.py': row}


def _rec(text):
    return {stamp.KEY_BODY: stamp.sha(text), stamp.KEY_BY: 'solai@0.33.0'}


def group_copied(s):
    """CP-43 to CP-48: what happens to a file the package ships and the vault runs.

    The branch had three fates and needed six. It hashed the shipped source against the file
    and called every difference `LOCAL`, which is right for a file the vault edited and wrong
    for the ordinary case, the package changing it. With no record of what was last put there
    those two are one observation, and resolving them towards never writing made every fix to
    a shipped script undeliverable to every vault that already existed: nine files in the
    Solai vault were reported `LOCAL` on the day `RES-011` shipped, and not one was edited.
    """
    tmp = tempfile.mkdtemp(prefix='solai-copied-')
    try:
        act, st, target = _copied_case(tmp, 'absent')
        s.ok('CP-43', 'an absent copied file is copied in, and the bytes recorded',
             act.kind == fsplan.COPY
             and st.next.get(target, {}).get(stamp.KEY_BODY) == stamp.sha(SHIPPED),
             repr((act.kind, st.next)))

        act, st, target = _copied_case(tmp, 'same', here=SHIPPED)
        s.ok('CP-44', 'no record and identical to what is shipped is adopted: NOOP, recorded',
             act.kind == fsplan.NOOP and act.verdict == 'FOREIGN'
             and target in st.next, repr((act.kind, act.verdict, st.next)))

        act, st, target = _copied_case(tmp, 'unknown', here='# somebody else entirely\n')
        s.ok('CP-45', 'no record and different is FOREIGN: skipped, and not claimed',
             act.kind == fsplan.SKIP and act.verdict == 'FOREIGN' and st.next == {},
             repr((act.kind, act.verdict, st.next)))

        # The fate that did not exist. This is the whole of GAP-012.
        act, st, target = _copied_case(tmp, 'moved', here=SHIPPED, shipped=MOVED,
                                       record=_rec(SHIPPED))
        s.ok('CP-46', 'a recorded file nobody edited, whose source moved, is UPDATED rather '
                      'than reported as the vault\'s own',
             act.kind == fsplan.COPY and act.verdict == 'UPDATED'
             and st.next.get(target, {}).get(stamp.KEY_BODY) == stamp.sha(MOVED),
             repr((act.kind, act.verdict, st.next)))

        act, st, target = _copied_case(tmp, 'edited', here=SHIPPED + '# mine\n',
                                       shipped=MOVED, record=_rec(SHIPPED))
        s.ok('CP-47', 'a recorded file edited here is LOCAL, skipped, and keeps its old record',
             act.kind == fsplan.SKIP and act.verdict == 'LOCAL'
             and st.next[target] == _rec(SHIPPED),
             repr((act.kind, act.verdict, st.next)))

        # Forcing by artefact id would take all of them; the path is what the plan row prints.
        act, st, target = _copied_case(tmp, 'forced', here=SHIPPED + '# mine\n', shipped=MOVED,
                                       record=_rec(SHIPPED), force=('_system/scripts/thing.py',))
        act2, _st2, _t2 = _copied_case(tmp, 'sibling', here=SHIPPED + '# mine\n', shipped=MOVED,
                                       record=_rec(SHIPPED), force=('_system/scripts/other.py',))
        s.ok('CP-48', '--force takes a copied file by its own path, and leaves its siblings',
             act.kind == fsplan.COPY and act2.kind == fsplan.SKIP,
             repr((act.kind, act2.kind)))

        # RES-014. The row that repeated forever, and the exit it never had.
        mine = '# somebody else entirely\n'
        act, st, target = _copied_case(tmp, 'signed', here=mine, signed=_sig(mine))
        s.ok('CP-49', 'a file somebody signed for is ADOPTED rather than FOREIGN, still '
                      'skipped, and still not claimed by the package',
             act.kind == fsplan.SKIP and act.verdict == engine.ADOPTED
             and 'CHG-132' in act.reason and st.next == {},
             repr((act.kind, act.verdict, act.reason, st.next)))

        act, st, target = _copied_case(tmp, 'signed-then-edited', here=mine + '# more\n',
                                       signed=_sig(mine))
        s.ok('CP-50', 'the signature is over the bytes it was given for: edit the file again '
                      'and it reads FOREIGN once more',
             act.kind == fsplan.SKIP and act.verdict == 'FOREIGN',
             repr((act.kind, act.verdict, act.reason)))

        act, st, target = _copied_case(tmp, 'signed-package-moved', here=mine, shipped=MOVED,
                                       signed=_sig(mine, package_sha=stamp.sha(SHIPPED)))
        s.ok('CP-51', 'a signed file whose package version has moved since says so, and is '
                      'still not overwritten',
             act.kind == fsplan.SKIP and act.verdict == engine.ADOPTED
             and 'changed it since' in act.reason, repr((act.verdict, act.reason)))

        act, st, target = _copied_case(tmp, 'signed-local', here=SHIPPED + '# mine\n',
                                       shipped=MOVED, record=_rec(SHIPPED),
                                       signed=_sig(SHIPPED + '# mine\n'))
        s.ok('CP-52', 'a recorded file this vault edited can be signed for too, and keeps its '
                      'old record',
             act.kind == fsplan.SKIP and act.verdict == engine.ADOPTED
             and st.next[target] == _rec(SHIPPED), repr((act.verdict, st.next)))

        act, st, target = _copied_case(tmp, 'skip-remembers', here=mine)
        s.ok('CP-53', 'a skipped row remembers the source it would have copied, the sha it '
                      'would have written, and the sha a signature must carry, which is what '
                      '--diff and --adopt read instead of working it out a second time',
             act.content and os.path.exists(act.content) and act.src == stamp.sha(SHIPPED)
             and act.sign == stamp.sha(mine),
             repr((act.content, act.src, act.sign)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_compiled, group_merge, group_predates, group_folders,
          group_shared, group_unstamped, group_copied)
