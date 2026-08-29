# -*- coding: utf-8 -*-
"""16 assertions on the authoring verbs: the renderers, the wiring, and the refusals.

The authoring script is the one part of the package that WRITES INTO THE PACKAGE, so its
failure mode is worse than a bad projection: it can leave the declarations in a state where
nothing loads and the next person meets a broken engine with no explanation. Hence `AU-06`,
which is the rule the whole script is shaped around - a declaration reaches disk only if it
loads first.

`AU-16` is a regression. `kind` meant two things in the first draft: the subcommand (`agent`
or `workflow`) and an agent's declared RETURN kind. The generic argument parser wrote
`kind = "agent"` into the `[returns]` block, and the loader refused it - which is the trap the
handoff names about a name that means two things, in the tool built to reduce hand-editing.
"""
import io
import os
import shutil
import sys
import tempfile

from lib import decl

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, 'skills', 'solai'))

import author as AU                                                 # noqa: E402

EXPECTED = 16
NAME = 'authoring'

AGENT_ARGS = {
    'job': 'A fixture job, written long enough to clear the minimum length the loader imposes.',
    'sent-when': 'In a test.',
    'returns': ['name=rows;type=list<str>;required=true;meaning=The rows it found.',
                'name=band;type=enum;values=high,low;required=false;meaning=A band.'],
    'evals': ['id=AU-1;asserts=Something checkable.;fails_when=It is not the case.'],
    'tools': ['Read'],
    'refuses': ['Doing anything real.'],
    'induces': 'nothing-in-particular',
}

WF_ARGS = {
    'goal': 'A fixture goal, long enough to clear the minimum the loader imposes on it here.',
    'input': 'Some items.',
    'output': 'Some results.',
    'phases': ['title=One;agent=scout;shape=pipeline;over=each item;carry=findings',
               'title=Two;agent=refuter;shape=pipeline;over=each finding'],
}


def _load(text, tmp, kind, name='probe'):
    p = os.path.join(tmp, '%s.toml' % name)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(text)
    return (decl.load_agent if kind == 'agent' else decl.load_workflow)(p)


def group_render(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-au-')
    try:
        s.eq('AU-01', 'a key=value;key=value spec parses into its pairs',
             AU._kv('name=rows;type=list<str>;required=true'),
             {'name': 'rows', 'type': 'list<str>', 'required': 'true'})

        s.ok('AU-02', 'a rendered TOML string escapes quotes and collapses newlines',
             AU._toml_str('he said "no"\nand left  ') == '"he said \\"no\\" and left"',
             repr(AU._toml_str('he said "no"\nand left  ')))

        a = _load(AU.agent_toml('probe', dict(AGENT_ARGS)), tmp, 'agent')
        s.ok('AU-03', 'the rendered agent declaration loads and carries what was asked for',
             a.name == 'probe' and [r.name for r in a.returns] == ['rows', 'band']
             and a.field('band').values == ['high', 'low']
             and len(a.evals) == 1 and a.evals[0].fails_when == 'It is not the case.',
             repr([r.name for r in a.returns]))

        s.ok('AU-04', 'an agent defaults to read-only with three read tools',
             not a.writes and a.tools == ['Read'] and a.induces == 'nothing-in-particular'
             and decl.load_agent.__name__ == 'load_agent', repr(a.tools))

        w = _load(AU.workflow_toml('probe-flow', dict(WF_ARGS)), tmp, 'workflow')
        s.ok('AU-05', 'the rendered workflow declaration loads with numbered phases',
             w.name == 'probe-flow' and [p.n for p in w.phases] == [1, 2]
             and w.phase('One').carry == 'findings' and w.agents == ['scout', 'refuter'],
             repr([(p.n, p.title) for p in w.phases]))

        bad = dict(AGENT_ARGS)
        bad['evals'] = []
        raised = []
        try:
            _load(AU.agent_toml('probe', bad), tmp, 'agent', 'probe-noeval')
        except decl.DeclError as e:
            raised = e.errors
        s.ok('AU-06', 'a declaration the loader would refuse is caught before it is planned',
             any('no `[[evals]]`' in x for x in raised),
             'the script validates in a temp file first, so a broken declaration never lands')

        barrier = dict(WF_ARGS)
        barrier['phases'] = [
            'title=One;agent=scout;shape=pipeline;over=each item;carry=findings',
            'title=Two;agent=refuter;shape=barrier;over=all of them;'
            'because=The whole set has to be present at once for this to mean anything.']
        wb = _load(AU.workflow_toml('probe-barrier', barrier), tmp, 'workflow', 'probe-barrier')
        s.ok('AU-07', '`because=` on a phase renders as barrier_because',
             wb.phase('Two').is_barrier and wb.phase('Two').barrier_because.startswith('The whole'),
             repr(wb.phase('Two').barrier_because))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_wiring(s):
    MAN = ('schema = 1\narchetype = "x"\n\nclasses = ["a"]\nagents = ["scout"]\n'
           'workflows = []\n\n[interview]\nasks = []\n')

    out, err = AU.add_to_list(MAN, 'agents', 'probe')
    s.ok('AU-08', 'a name is appended inside the existing top-level list line',
         err is None and 'agents = ["scout", "probe"]' in out, repr(out))

    out2, err2 = AU.add_to_list(MAN, 'workflows', 'probe')
    s.ok('AU-09', 'an empty list gains its first entry without a stray comma',
         err2 is None and 'workflows = ["probe"]' in out2, repr(out2))

    _, err3 = AU.add_to_list(MAN, 'agents', 'scout')
    s.eq('AU-10', 'a name already listed is reported, not duplicated', err3, 'already listed')

    _, err4 = AU.add_to_list(MAN, 'lookups', 'probe')
    s.ok('AU-11', 'a missing list line is refused rather than invented',
         err4 and 'no top-level' in err4, repr(err4))

    s.ok('AU-12', 'the edit stays above the first table header, where TOML keeps it top-level',
         out.index('agents = ') < out.index('[interview]'),
         'a list written below a table header is swallowed into that table')


def group_refusals(s):
    s.ok('AU-13', 'the shipped names are all taken, and an unused one is free',
         AU.name_taken('scout') and AU.name_taken('review') and AU.name_taken('gap')
         and AU.name_taken('a-name-nothing-uses') is None,
         'an agent, a workflow and a card class share one namespace')

    dup = ('Read the sources you are pointed at and report every candidate of the kind you were '
           'asked for, each with the place it was found and the words that carry it.')
    s.ok('AU-14', 'a job that restates an existing agent\'s job is refused, naming it',
         (AU.job_overlap(dup) or '').find('scout') >= 0, repr(AU.job_overlap(dup)))

    fresh = ('Convert a bank statement PDF into ledger lines and reconcile the total against the '
             'closing balance printed on the statement itself.')
    s.eq('AU-15', 'a genuinely different job is not refused', AU.job_overlap(fresh), None)

    rendered = AU.agent_toml('probe', dict(AGENT_ARGS, **{'verb': 'agent'}))
    s.ok('AU-16', 'the subcommand never leaks into the declared return kind',
         'kind    = "records"' in rendered and 'kind    = "agent"' not in rendered,
         'one word meaning two things wrote kind = "agent" into [returns] in the first draft')


GROUPS = (group_render, group_wiring, group_refusals)
