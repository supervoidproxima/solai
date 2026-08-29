# -*- coding: utf-8 -*-
"""49 assertions on the declaration loader: 20 on a single class, 29 on an archetype set.

The loader is the only thing standing between a malformed declaration and six projections
that disagree with each other. Every negative case here asserts the MESSAGE as well as the
refusal, because a loader that fails for the wrong reason is indistinguishable from one that
fails for the right reason until the day the reason matters.

Three of these are regressions of failures that actually happened and were expensive:

  - `DA-08`/`DA-09`: a bare key written after a table header is silently swallowed by TOML, so
    `classes = [...]` below `[ids]` becomes `ids.classes` and the archetype loads with nothing
    in it. Silent is the whole problem.
  - `DA-10`: `[[pipeline]]` was renamed `[[loop]]`; a manifest still carrying the old key would
    load with an empty loop and render an empty section rather than failing.
  - `DA-14`: the `role` archetype declared class folders under no folder the manifest declared.

The real four archetypes are loaded too (`DA-02`, `DA-03`, `DA-04`). Fixtures prove the loader;
only the real manifests prove the package ships loadable declarations.
"""
import os
import shutil
import tempfile

from lib import decl

EXPECTED = 50
NAME = 'declarations'

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------- fixtures

CLASS_OK = '''\
schema = 1
class     = "alpha"
prefix    = "ALP"
folder    = "cards/alpha"
skill     = "alpha"
title     = "Alpha"
purpose   = "A fixture class."

[status]
lifecycle = ["open", "working"]
terminal  = ["closed"]
default   = "open"

[[fields]]
name     = "title"
type     = "scalar"
card     = "1"
required = true

[[fields]]
name    = "track"
type    = "list<wl>"
card    = "0..N"
source  = "partition"
'''

MANIFEST_OK = '''\
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


def _write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def _class(toml_text, tmp, name='alpha'):
    """Write one class TOML to a temp file and return its path."""
    p = os.path.join(tmp, '%s.toml' % name)
    _write(p, toml_text)
    return p


def _pkg(tmp, manifest=MANIFEST_OK, classes=None, common=None, arch='fixture'):
    """Build a throwaway package root and return (pkg_root, archetype_name)."""
    root = tempfile.mkdtemp(prefix='solai-test-pkg-', dir=tmp)
    _write(os.path.join(root, 'archetypes', arch, 'manifest.toml'), manifest)
    for cname, text in (classes if classes is not None else {'alpha': CLASS_OK}).items():
        _write(os.path.join(root, 'archetypes', arch, 'classes', '%s.toml' % cname), text)
    for cname, text in (common or {}).items():
        _write(os.path.join(root, 'common', 'classes', '%s.toml' % cname), text)
    return root, arch


def _swap(text, old, new):
    assert old in text, 'fixture edit found no %r' % old
    return text.replace(old, new, 1)


# --------------------------------------------------------------------------- one class

def group_class(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-cls-')
    try:
        def load(text, name='alpha'):
            return lambda: decl.load_class(_class(text, tmp, name))

        c = decl.load_class(_class(CLASS_OK, tmp))
        s.ok('DC-01', 'a well-formed class loads and carries its identity',
             (c.name, c.prefix, c.folder, c.skill) == ('alpha', 'ALP', 'cards/alpha', 'alpha'),
             repr((c.name, c.prefix, c.folder, c.skill)))

        s.ok('DC-02', 'statuses concatenate lifecycle then terminal, and the accessors resolve',
             c.statuses == ['open', 'working', 'closed']
             and c.field('title') is not None and c.field('nope') is None
             and c.link('nope') is None, repr(c.statuses))

        s.ok('DC-03', 'is_list is true for a list<> type and false for a scalar',
             c.field('track').is_list and not c.field('title').is_list)

        s.raises('DC-04', 'a class with no `class` key is refused by name',
                 load(_swap(CLASS_OK, 'class     = "alpha"', '')), 'no `class` key')

        s.raises('DC-05', 'a class with no `prefix` is refused',
                 load(_swap(CLASS_OK, 'prefix    = "ALP"', '')), 'no `prefix`')

        s.raises('DC-06', 'a prefix that is not uppercase letters is refused',
                 load(_swap(CLASS_OK, '"ALP"', '"Al1"')), 'must be uppercase letters only')

        s.raises('DC-07', 'a class with no `folder` is refused',
                 load(_swap(CLASS_OK, 'folder    = "cards/alpha"', '')), 'no `folder`')

        s.raises('DC-08', 'a class with no status values cannot satisfy D2 and is refused',
                 load(_swap(CLASS_OK,
                            'lifecycle = ["open", "working"]\nterminal  = ["closed"]',
                            'lifecycle = []\nterminal  = []')),
                 'no status values')

        s.raises('DC-09', 'a default status outside lifecycle and terminal is refused',
                 load(_swap(CLASS_OK, 'default   = "open"', 'default   = "ghost"')),
                 'is not in lifecycle or terminal')

        s.raises('DC-10', 'a status declared both live and terminal is refused',
                 load(_swap(CLASS_OK, 'terminal  = ["closed"]', 'terminal  = ["open"]')),
                 'declared both live and terminal')

        s.raises('DC-11', 'a field declared twice is refused',
                 load(CLASS_OK + '\n[[fields]]\nname = "title"\ntype = "scalar"\n'),
                 "field 'title' declared twice")

        s.raises('DC-12', 'an unknown field type is refused and the known ones are listed',
                 load(_swap(CLASS_OK, 'type     = "scalar"', 'type     = "text"')),
                 ('unknown type', 'Known:'))

        s.raises('DC-13', 'an enum with neither values nor a source is refused',
                 load(CLASS_OK + '\n[[fields]]\nname = "band"\ntype = "enum"\n'),
                 'declares no values and no source')

        s.accepts('DC-14', 'an enum whose values arrive from a source is accepted',
                  load(CLASS_OK + '\n[[fields]]\nname = "band"\ntype = "enum"\n'
                                  'source = "partition"\n'))

        s.raises('DC-15', 'a field that is both required and derived is refused',
                 load(CLASS_OK + '\n[[fields]]\nname = "demand"\ntype = "enum"\n'
                                 'values = ["low"]\nrequired = true\nderived_by = "script"\n'),
                 'both required and derived')

        s.raises('DC-16', 'an underscore in a field name is refused: keys are kebab-case',
                 load(CLASS_OK + '\n[[fields]]\nname = "settled_on"\ntype = "date"\n'),
                 'uses an underscore')

        s.raises('DC-17', 'a name declared as both a field and a link is refused',
                 load(CLASS_OK + '\n[[links]]\nfield = "title"\ntarget = "alpha"\n'
                                 'kind = "lateral"\n'),
                 'declared as both a field and a link')

        s.raises('DC-18', 'an unknown link kind is refused and the known ones are listed',
                 load(CLASS_OK + '\n[[links]]\nfield = "beta"\ntarget = "beta"\n'
                                 'kind = "sideways"\n'),
                 ('unknown kind', 'Known:'))

        s.raises('DC-19', 'a bidirectional link naming no reciprocal field is refused',
                 load(CLASS_OK + '\n[[links]]\nfield = "beta"\ntarget = "beta"\n'
                                 'kind = "bidirectional"\n'),
                 'names no reciprocal field')

        s.raises('DC-20', 'a lateral link targeting another class is refused: lateral is same-class',
                 load(CLASS_OK + '\n[[links]]\nfield = "beta"\ntarget = "beta"\n'
                                 'kind = "lateral"\n'),
                 'Lateral means same-class')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- archetype set

def group_archetype(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-arch-')
    try:
        def load(manifest=MANIFEST_OK, classes=None, common=None, arch='fixture'):
            root, name = _pkg(tmp, manifest, classes, common, arch)
            return lambda: decl.load_archetype(root, name)

        s.raises('DA-01', 'an archetype that does not exist is refused, naming the path looked for',
                 lambda: decl.load_archetype(PKG_ROOT, 'no-such-archetype'),
                 'no archetype')

        real = {}
        for name in ('minimal', 'project', 'personal', 'role'):
            real[name] = decl.load_archetype(PKG_ROOT, name)
        s.ok('DA-02', 'all four shipped archetypes load with every class they declare',
             sorted(real) == ['minimal', 'personal', 'project', 'role'], repr(sorted(real)))

        counts = tuple(len(real[n].classes) for n in ('minimal', 'project', 'personal', 'role'))
        s.eq('DA-03', 'the shipped class counts are 0 / 5 / 5 / 3, so nothing was swallowed',
             counts, (0, 5, 5, 3))

        s.ok('DA-30', 'every shipped archetype declares the opening line of its own places',
             all((real[n].defaults.get('remit') or '').strip()
                 for n in ('minimal', 'project', 'personal', 'role')),
             repr({n: real[n].defaults.get('remit') for n in real}))

        loops = {n: len(real[n].loop) for n in ('project', 'personal', 'role')}
        s.ok('DA-04', 'every archetype that declares a way of working exposes it as `loop`',
             all(v > 0 for v in loops.values()), repr(loops))

        arch_root, arch_name = _pkg(tmp)
        arch = decl.load_archetype(arch_root, arch_name)
        s.ok('DA-05', 'a well-formed fixture archetype loads its classes, folders and loop',
             arch.name == 'fixture' and [c.name for c in arch.classes] == ['alpha']
             and len(arch.folders) == 2 and arch.loop[0]['n'] == 1
             and arch.default_tier == 'light', repr(arch.raw.keys()))

        s.raises('DA-06', 'an archetype whose declared name does not match its folder is refused',
                 load(_swap(MANIFEST_OK, 'archetype = "fixture"', 'archetype = "other"')),
                 'but lives in')

        s.raises('DA-07', 'an unknown default governance tier is refused',
                 load(_swap(MANIFEST_OK, 'governance_tier = "light"',
                            'governance_tier = "ultra"')),
                 'unknown default tier')

        swallowed_ids = _swap(MANIFEST_OK, 'classes = ["alpha"]\nlookups = []\n', '')
        swallowed_ids = _swap(swallowed_ids, '[ids]\n', '[ids]\nclasses = ["alpha"]\n')
        s.raises('DA-08', 'a `classes` key swallowed by [ids] is named, not silently empty',
                 load(swallowed_ids), ('is nested under `[ids]`', 'TOML swallows them'))

        swallowed_int = _swap(MANIFEST_OK, 'classes = ["alpha"]\nlookups = []\n', '')
        swallowed_int = _swap(swallowed_int, '[interview]\n',
                              '[interview]\nclasses = ["alpha"]\n')
        s.raises('DA-09', 'the same swallowing under [interview] is named too',
                 load(swallowed_int), 'is nested under `[interview]`')

        s.raises('DA-10', 'a manifest still carrying the renamed `[[pipeline]]` key is refused',
                 load(MANIFEST_OK + '\n[[pipeline]]\nn = 1\nname = "stale key"\n'),
                 ('`[[pipeline]]` was renamed to `[[loop]]`', 'would render empty'))

        no_classes = _swap(MANIFEST_OK, 'classes = ["alpha"]', 'classes = []')
        no_classes += ('\n[[artefacts]]\nid = "card-skills"\npath = ".claude/skills/{skill}/'
                       'SKILL.md"\nmode = "merged"\nemitter = "cardskill"\nforeach = "classes"\n')
        s.raises('DA-11', 'a card-skills artefact with no classes would generate nothing: refused',
                 load(no_classes, classes={}), 'but no classes')

        beta_dup_prefix = _swap(_swap(CLASS_OK, '"alpha"', '"beta"'),
                                'folder    = "cards/alpha"', 'folder    = "cards/beta"')
        s.raises('DA-12', 'two classes claiming one prefix are refused: one prefix, one minter',
                 load(_swap(MANIFEST_OK, 'classes = ["alpha"]', 'classes = ["alpha", "beta"]'),
                      classes={'alpha': CLASS_OK, 'beta': beta_dup_prefix}),
                 ('claimed by both', 'one minter'))

        beta_dup_folder = _swap(_swap(CLASS_OK, '"alpha"', '"beta"'), '"ALP"', '"BET"')
        s.raises('DA-13', 'two classes claiming one folder are refused: ownership must be decidable',
                 load(_swap(MANIFEST_OK, 'classes = ["alpha"]', 'classes = ["alpha", "beta"]'),
                      classes={'alpha': CLASS_OK, 'beta': beta_dup_folder}),
                 'Ownership of a path must be decidable')

        s.raises('DA-14', 'a class folder under no folder the manifest declares is refused',
                 load(classes={'alpha': _swap(CLASS_OK, 'folder    = "cards/alpha"',
                                              'folder    = "elsewhere/alpha"')}),
                 'which is under no folder the manifest declares')

        s.raises('DA-15', 'a link targeting a class nobody declared is refused',
                 load(classes={'alpha': CLASS_OK + '\n[[links]]\nfield = "ghost"\n'
                                                   'target = "ghost"\nkind = "one-way"\n'}),
                 'not a declared class or lookup')

        beta_plain = _swap(_swap(_swap(CLASS_OK, '"alpha"', '"beta"'), '"ALP"', '"BET"'),
                           'folder    = "cards/alpha"', 'folder    = "cards/beta"')
        two = _swap(MANIFEST_OK, 'classes = ["alpha"]', 'classes = ["alpha", "beta"]')
        alpha_bidi = (CLASS_OK + '\n[[links]]\nfield = "beta"\ntarget = "beta"\n'
                                 'kind = "bidirectional"\nreciprocal = "alpha"\n')
        s.raises('DA-16', 'a bidirectional link whose reciprocal is not declared back is refused',
                 load(two, classes={'alpha': alpha_bidi, 'beta': beta_plain}),
                 'declares no such link')

        beta_wrong = beta_plain + ('\n[[links]]\nfield = "alpha"\ntarget = "beta"\n'
                                   'kind = "lateral"\n')
        s.raises('DA-17', 'a reciprocal that points at the wrong class is refused',
                 load(two, classes={'alpha': alpha_bidi, 'beta': beta_wrong}),
                 'but it points at')

        s.raises('DA-18', 'classes disagreeing on cite_style are refused: one vault, one convention',
                 load(two, classes={
                     'alpha': CLASS_OK + '\n[body]\ncite_style = "footnotes"\n',
                     'beta': beta_plain + '\n[body]\ncite_style = "inline-wikilink"\n'}),
                 'disagree on cite_style')

        common_class = _swap(_swap(_swap(CLASS_OK, '"alpha"', '"shared"'), '"ALP"', '"SHR"'),
                             'folder    = "cards/alpha"', 'folder    = "cards/shared"')
        root, name = _pkg(tmp, _swap(MANIFEST_OK, 'classes = ["alpha"]',
                                     'classes = ["alpha", "shared"]'),
                          classes={'alpha': CLASS_OK}, common={'shared': common_class})
        resolved = decl.load_archetype(root, name)
        s.ok('DA-19', 'a class not present in the archetype resolves from common/classes',
             [c.name for c in resolved.classes] == ['alpha', 'shared'],
             repr([c.name for c in resolved.classes]))

        # ------------------------------------------------------- agents on an archetype
        picked = tuple(tuple(a.name for a in real[n].agents)
                       for n in ('minimal', 'project', 'personal', 'role'))
        s.eq('DA-20', 'each archetype takes its own selection from the one shared roster',
             picked,
             ((),
              ('scout', 'refuter', 'extractor', 'editor', 'reconciler'),
              ('extractor', 'editor'),
              ('scout', 'refuter', 'extractor', 'editor')))

        s.ok('DA-21', 'a shared agent resolves from common/agents without living in the archetype',
             all(os.path.join('common', 'agents') in a.path.replace('/', os.sep)
                 for n in ('project', 'personal', 'role') for a in real[n].agents),
             'one declaration per agent was the whole point of shared-roster selection')

        with_agent = _swap(MANIFEST_OK, 'lookups = []', 'lookups = []\nagents = ["probe"]')
        probe = ('schema = 1\nagent = "probe"\njob = "A fixture job long enough to clear the '
                 'minimum the loader imposes on it."\ntools = ["Read"]\n\n[returns]\n'
                 'kind = "report"\n\n[[returns.fields]]\nname = "text"\ntype = "scalar"\n'
                 'required = true\n\n[[evals]]\nid = "P-1"\nasserts = "x"\nfails_when = "y"\n')

        def load_with_agent(manifest=with_agent, agents=None, classes=None):
            root, name = _pkg(tmp, manifest, classes)
            for aname, text in (agents if agents is not None else {'probe': probe}).items():
                _write(os.path.join(root, 'common', 'agents', '%s.toml' % aname), text)
            return lambda: decl.load_archetype(root, name)

        s.accepts('DA-22', 'an archetype that declares an agent loads it through the same '
                           'archetype-then-common fallback the lookups use',
                  load_with_agent())

        s.raises('DA-23', 'an agent listed in the manifest but absent on disk is refused',
                 load_with_agent(agents={}), ('agents lists', 'does not exist'))

        swallowed = _swap(MANIFEST_OK, 'lookups = []\n', '')
        swallowed = _swap(swallowed, '[ids]\n', '[ids]\nagents = ["probe"]\n')
        s.raises('DA-24', 'an `agents` key swallowed by [ids] is named like the others',
                 load_with_agent(manifest=swallowed),
                 ('`agents` is nested under `[ids]`', 'TOML swallows them'))

        # ---------------------------------------------------- workflows on an archetype
        picked_wf = tuple(tuple(w.name for w in real[n].workflows)
                          for n in ('minimal', 'project', 'personal', 'role'))
        s.eq('DA-25', 'workflows are selected per archetype from the shared set, like the agents',
             picked_wf,
             ((), ('review', 'intake', 'polish'), (), ('intake', 'polish')))

        s.ok('DA-26', 'every phase of every shipped workflow calls an agent its archetype takes',
             all(p.agent in [a.name for a in real[n].agents]
                 for n in ('project', 'role') for w in real[n].workflows for p in w.phases),
             'otherwise the projected script names a subagent the place does not have')

        wf_manifest = _swap(MANIFEST_OK, 'lookups = []',
                            'lookups = []\nagents = ["probe"]\nworkflows = ["probe-flow"]')
        probe_agent = ('schema = 1\nagent = "probe"\njob = "A fixture job long enough to clear '
                       'the minimum the loader imposes on it."\ntools = ["Read"]\n\n[returns]\n'
                       'kind = "records"\n\n[[returns.fields]]\nname = "rows"\n'
                       'type = "list<str>"\nrequired = true\n\n[[evals]]\nid = "P-1"\n'
                       'asserts = "x"\nfails_when = "y"\n')

        def load_flow(phases, manifest=wf_manifest, agent_toml=probe_agent):
            root, name = _pkg(tmp, manifest, None)
            _write(os.path.join(root, 'common', 'agents', 'probe.toml'), agent_toml)
            _write(os.path.join(root, 'common', 'workflows', 'probe-flow.toml'),
                   'schema = 1\nworkflow = "probe-flow"\ngoal = "A fixture goal long enough to '
                   'clear the minimum the loader imposes."\ninput = "Items."\n'
                   'output = "Results."\n' + phases)
            return lambda: decl.load_archetype(root, name)

        two_probe = ('\n[[phases]]\nn = 1\ntitle = "One"\nagent = "probe"\nshape = "pipeline"\n'
                     'over = "each item"\ncarry = "rows"\n'
                     '\n[[phases]]\nn = 2\ntitle = "Two"\nagent = "probe"\nshape = "pipeline"\n'
                     'over = "each row"\n')
        s.accepts('DA-27', 'a workflow whose phases call a declared agent loads', load_flow(two_probe))

        ghost = two_probe.replace('agent = "probe"\nshape = "pipeline"\nover = "each row"',
                                  'agent = "ghost"\nshape = "pipeline"\nover = "each row"')
        s.raises('DA-28', 'a phase calling an agent the archetype does not take is refused',
                 load_flow(ghost), ('calls agent', 'this archetype does not declare'))

        bad_carry = two_probe.replace('carry = "rows"', 'carry = "nope"')
        s.raises('DA-29', 'a carry naming a field the agent does not return is refused',
                 load_flow(bad_carry), ('carries', 'does not\n' if False else 'does not'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_class, group_archetype)
