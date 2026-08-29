# -*- coding: utf-8 -*-
"""34 assertions on the workflow layer: 22 on the declaration, 12 on the emitter.

The workflow layer is where a wrong projection is most expensive, because a bad script RUNS.
Three assertions here exist because the first projection I read had exactly those defects:

  - `WE-06`: the carry chain was named for two phases and read the wrong variable at three, which
    two-phase declarations hid completely.
  - `WE-08`: a non-first stage interpolated result OBJECTS into its prompt, so the second agent
    would have been asked to work on `[object Object]` - and would have done it.
  - `WE-10`: the `// ` marker prefix was not accepted by the shared region reader, so the engine
    could not find the markers in its own output. This asserts the reader and the prefix agree.

`WE-09` guards resume: wall-clock or randomness anywhere in a script shortens the reusable
prefix to nothing, so their absence is asserted rather than assumed.
"""
import os
import shutil
import tempfile

from lib import decl, regions
from lib.emit import workflow as EW

EXPECTED = 34
NAME = 'workflows'

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPPED = ('intake', 'polish', 'review')

WF_OK = '''\
schema = 1
workflow = "probe-job"
title    = "Probe Job"
goal     = "A fixture workflow whose goal is long enough to clear the loader's minimum length."
input    = "Some items to work through."
output   = "Whatever the last phase returned."
run_when = "In a test."

[[phases]]
n      = 1
title  = "First"
agent  = "scout"
shape  = "pipeline"
over   = "each item"
carry  = "findings"
detail = "Find the things."

[[phases]]
n      = 2
title  = "Second"
agent  = "refuter"
shape  = "pipeline"
over   = "each finding"
detail = "Attack the things."
'''

BARRIER_PHASE = '''
[[phases]]
n               = 3
title           = "Third"
agent           = "editor"
shape           = "barrier"
over            = "everything at once"
barrier_because = "The whole set has to be seen together for this to mean anything at all."
detail          = "Settle it."
'''


def _swap(text, old, new):
    assert old in text, 'fixture edit found no %r' % old
    return text.replace(old, new, 1)


def _wf(text, tmp, name='probe-job'):
    p = os.path.join(tmp, '%s.toml' % name)
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return p


def _agents():
    return {n: decl.load_agent(os.path.join(PKG_ROOT, 'common', 'agents', '%s.toml' % n))
            for n in ('scout', 'refuter', 'extractor', 'editor')}


# --------------------------------------------------------------------------- declaration

def group_declaration(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-wf-')
    try:
        def load(text):
            return lambda: decl.load_workflow(_wf(text, tmp))

        shipped = {n: decl.load_workflow(os.path.join(PKG_ROOT, 'common', 'workflows',
                                                      '%s.toml' % n)) for n in SHIPPED}
        s.ok('WD-01', 'all three shipped workflows load, each with at least two phases',
             sorted(shipped) == sorted(SHIPPED)
             and all(len(w.phases) >= 2 for w in shipped.values()),
             repr({k: len(v.phases) for k, v in shipped.items()}))

        s.ok('WD-02', 'exactly one shipped phase is a barrier, and it justifies itself',
             sum(1 for w in shipped.values() for p in w.phases if p.is_barrier) == 1
             and all(p.barrier_because for w in shipped.values() for p in w.phases
                     if p.is_barrier),
             'the default is a pipeline; a barrier that nobody has to argue for spreads')

        w = decl.load_workflow(_wf(WF_OK, tmp))
        s.ok('WD-03', 'a well-formed workflow loads and its accessors resolve',
             (w.name, w.title) == ('probe-job', 'Probe Job')
             and w.agents == ['scout', 'refuter']
             and w.phase('First').carry == 'findings' and w.phase('nope') is None,
             repr(w.agents))

        s.raises('WD-04', 'a workflow with no `workflow` key is refused by name',
                 load(_swap(WF_OK, 'workflow = "probe-job"', '')), 'no `workflow` key')

        s.raises('WD-05', 'a name that is not lowercase kebab-case is refused',
                 load(_swap(WF_OK, '"probe-job"', '"Probe_Job"')), 'lowercase kebab-case')

        s.raises('WD-06', 'a workflow with no goal cannot be judged finished, so it is refused',
                 load(_swap(WF_OK, 'goal     = "A fixture workflow whose goal is long enough to '
                                   "clear the loader's minimum length.\"", 'goal = ""')),
                 'no `goal`')

        s.raises('WD-07', 'a goal too short to name a finishable job is refused, with its length',
                 load(_swap(WF_OK, "A fixture workflow whose goal is long enough to clear the "
                                   "loader's minimum length.", 'Do the review.')),
                 ('names a topic rather than a', 'characters'))

        s.raises('WD-08', 'a workflow that does not say what it is given is refused',
                 load(_swap(WF_OK, 'input    = "Some items to work through."', 'input = ""')),
                 'no `input`')

        s.raises('WD-09', 'a workflow whose result is unnamed is refused',
                 load(_swap(WF_OK, 'output   = "Whatever the last phase returned."',
                            'output = ""')),
                 'no `output`')

        one_phase = WF_OK.split('[[phases]]')[0] + (
            '[[phases]]\nn = 1\ntitle = "Only"\nagent = "scout"\nshape = "pipeline"\n'
            'over = "each item"\n')
        s.raises('WD-10', 'a single-phase workflow is an agent call with ceremony, so it is refused',
                 load(one_phase), 'one agent call with ceremony')

        s.raises('WD-11', 'two phases with one title would merge in the progress report: refused',
                 load(_swap(WF_OK, 'title  = "Second"', 'title  = "First"')),
                 'two phases titled')

        s.raises('WD-12', 'a phase that names no agent is refused',
                 load(_swap(WF_OK, 'agent  = "refuter"', '')), 'names no agent')

        s.raises('WD-13', 'an unknown phase shape is refused and the known ones listed',
                 load(_swap(WF_OK, 'shape  = "pipeline"', 'shape  = "fanout"')),
                 ('unknown shape', 'Known:'))

        s.raises('WD-14', 'a phase that does not say what it runs over is refused',
                 load(_swap(WF_OK, 'over   = "each item"', '')), 'does not say what it runs')

        no_reason = _swap(WF_OK + BARRIER_PHASE,
                          'barrier_because = "The whole set has to be seen together for this to '
                          'mean anything at all."\n', '')
        s.raises('WD-15', 'a barrier that does not justify itself is refused',
                 load(no_reason), ('gives no `barrier_because`', 'or it is a pipeline'))

        s.raises('WD-16', 'a barrier justified in a few words is a restatement, not a reason',
                 load(_swap(WF_OK + BARRIER_PHASE,
                            'The whole set has to be seen together for this to mean anything at '
                            'all.', 'It needs all.')),
                 'not a reason')

        s.raises('WD-17', 'a pipeline carrying `barrier_because` is refused: the keys disagree',
                 load(_swap(WF_OK, 'over   = "each finding"',
                            'over   = "each finding"\nbarrier_because = "Because the whole set '
                            'must be present at once for this."')),
                 'would be read by nothing')

        s.raises('WD-18', 'phase numbers with a gap are refused: they order the projection',
                 load(_swap(WF_OK, 'n      = 2', 'n      = 7')),
                 ('phase numbers are', 'order the projection'))

        all_barrier = _swap(WF_OK, 'shape  = "pipeline"\nover   = "each item"',
                            'shape  = "barrier"\nover   = "each item"\nbarrier_because = "Every '
                            'branch genuinely needs the whole prior set before starting."')
        all_barrier = _swap(all_barrier, 'shape  = "pipeline"\nover   = "each finding"',
                            'shape  = "barrier"\nover   = "each finding"\nbarrier_because = '
                            '"This one also genuinely needs the entire prior set present."')
        s.raises('WD-19', 'a workflow of nothing but barriers is refused: name the one that needs it',
                 load(all_barrier), 'every phase is a barrier')

        s.raises('WD-20', 'a non-last phase that declares no carry is refused',
                 load(_swap(WF_OK, 'carry  = "findings"\n', '')),
                 ('does not declare what it carries', '[object Object]'))

        s.raises('WD-21', 'a carry off the last phase is read by nothing, so it is refused',
                 load(_swap(WF_OK, 'over   = "each finding"',
                            'over   = "each finding"\ncarry  = "reasons"')),
                 'nothing consumes it')

        s.raises('WD-22', 'an unknown key is refused at the workflow and the phase level alike',
                 load(_swap(WF_OK, 'run_when = "In a test."',
                            'run_when = "In a test."\nresumable = true')),
                 ('unknown key', 'read by nothing'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- emitter

def group_emitter(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-we-')
    try:
        w = decl.load_workflow(_wf(WF_OK, tmp))
        agents = _agents()
        rt = EW.render_regions(w, agents)

        s.eq('WE-01', 'render_regions produces exactly the two declared regions',
             tuple(sorted(rt)), tuple(sorted(EW.REGIONS)))

        s.ok('WE-02', 'the meta literal carries the name, the goal and one entry per phase',
             "name: 'probe-job'" in rt['meta']
             and 'clear the loader' in rt['meta']
             and rt['meta'].count('"title"') == len(w.phases), repr(rt['meta'][:200]))

        sch = EW.schema_for(agents['scout'])
        s.ok('WE-03', 'every declared return type maps to its JSON Schema counterpart',
             sch['properties']['exhausted']['type'] == 'boolean'
             and sch['properties']['findings']['type'] == 'array'
             and sch['properties']['findings']['items']['required'] == ['where', 'quote', 'why']
             and 'findings' in sch['required'] and 'missed' not in sch['required'],
             repr(sch['properties'].keys()))

        vsch = EW.schema_for(agents['refuter'])
        s.ok('WE-04', 'an enum return field projects as an enum, not a bare string',
             vsch['properties']['verdict']['enum']
             == ['refuted', 'weakened', 'survives', 'undecidable'],
             repr(vsch['properties']['verdict']))

        s.ok('WE-05', 'the script declares one schema constant per distinct agent it calls',
             rt['script'].count('_RETURNS = {') == len(w.agents)
             and 'SCOUT_RETURNS' in rt['script'] and 'REFUTER_RETURNS' in rt['script'],
             repr(w.agents))

        s.ok('WE-06', 'the carry chain flatMaps the declared field and the next phase reads it',
             "flatMap((r) => r['findings'] ?? [])" in rt['script']
             and 'const carry1 =' in rt['script']
             and 'await pipeline(carry1,' in rt['script'],
             'named for two phases and read wrong at three, before this assertion existed')

        s.ok('WE-07', 'the first phase reads args.items and refuses to start without them',
             'await pipeline(args.items,' in rt['script']
             and 'Array.isArray(args.items)' in rt['script'], repr(rt['script'][:200]))

        s.ok('WE-08', 'objects are converted explicitly, never interpolated as [object Object]',
             'const asText =' in rt['script'] and 'asText(original ?? item)' in rt['script']
             and 'String(original ?? item)' not in rt['script'],
             'a stage that asks an agent to work on [object Object] runs anyway')

        injected = rt['script'] + '\nconst t = Date.now()\n'
        s.ok('WE-09', 'no projection carries a resume-breaking construct, and one is detected',
             not EW.forbidden_in(rt['script']) and not EW.forbidden_in(rt['meta'])
             and EW.forbidden_in(injected) == ['Date.now'],
             'wall-clock or randomness shortens the reusable prefix to nothing')

        body = EW.skeleton(w, agents, rt, src='abc123')
        found = regions.find_all(body)
        s.ok('WE-10', 'the // marker prefix is readable by the shared region reader',
             sorted(found) == sorted(EW.REGIONS)
             and all(found[r].verdict('abc123') == 'CLEAN' for r in EW.REGIONS),
             'the prefix and its reader are one unit: markers nothing can find break the merge')

        ok, n, advice = EW.check_size(body, w)
        over_ok, over_n, over_advice = EW.check_size('x\n' * 300, w)
        s.ok('WE-11', 'the projection is under the line cap, and going over is refused by name',
             ok and n <= EW.LINE_CAP and not over_ok
             and '.claude/workflows/probe-job.js' in over_advice
             and 'no filesystem access' in over_advice, repr((n, over_advice[:80])))

        # Adding a third phase makes the second one a middle phase, so it now needs a carry of
        # its own. The loader refuses the fixture otherwise, which is the rule working.
        three = _swap(WF_OK + BARRIER_PHASE, 'over   = "each finding"',
                      'over   = "each finding"\ncarry  = "reasons"')
        barrier = decl.load_workflow(_wf(three, tmp, 'probe-barrier'))
        brt = EW.render_regions(barrier, agents)
        s.ok('WE-12', 'a barrier phase emits parallel() and carries its reason into the script',
             'await parallel([' in brt['script']
             and '// Barrier, and the declaration says why:' in brt['script']
             and 'await pipeline(' in brt['script'],
             'the justification travels with the code that pays for it')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_declaration, group_emitter)
