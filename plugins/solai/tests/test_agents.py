# -*- coding: utf-8 -*-
"""34 assertions on the agent layer: 22 on the declaration, 12 on the emitter.

An agent is a declared artefact of an archetype, exactly like a card class, so it earns the
same treatment: refuse a malformed declaration by name, and prove the projection is derived
rather than written.

Two families of refusal are worth naming, because both are about silence rather than error:

  - `DG-20` to `DG-22`: an UNKNOWN key is refused. A key that is read by nothing looks like it
    took effect and never says otherwise - the same silent failure as a bare key swallowed by
    a TOML table header. This was written after a stray `whenever =` was typed into
    `scout.toml` and the loader accepted it without a word.
  - `DG-18`: an eval with no `fails_when` is refused. An eval that cannot fail is a
    description of intentions, and a roster of those is machinery asserting what it cannot
    show, which is what D1 exists to forbid.

`EA-11` is the structural half of the single-writer rule: nothing an agent projects may carry
an id or claim a folder, because an agent that minted would quietly become a second minter of
a prefix that already has one.
"""
import os
import shutil
import tempfile

from lib import decl, regions
from lib.emit import agent as EA
from lib.emit import load_labels

EXPECTED = 34
NAME = 'agents'

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPPED = ('scout', 'refuter', 'extractor', 'editor', 'reconciler')

AGENT_OK = '''\
schema = 1
agent     = "probe"
title     = "Probe"
job       = "A fixture job, written long enough to clear the minimum length the loader imposes."
sent_when = "In a test."
model     = "inherit"
tools     = ["Read", "Grep"]
writes    = false
induces   = "none"
reads     = ["the fixture"]
refusals  = ["Doing anything real."]

[returns]
kind    = "records"
meaning = "Fixture records."

[[returns.fields]]
name     = "findings"
type     = "list<obj>"
required = true
of       = ["where", "quote"]
meaning  = "Fixture findings."

[[returns.fields]]
name     = "band"
type     = "enum"
required = false
values   = ["high", "low"]
meaning  = "A fixture band."

[[evals]]
id         = "PB-1"
asserts    = "Something checkable."
fails_when = "It is not the case."
'''


def _swap(text, old, new):
    assert old in text, 'fixture edit found no %r' % old
    return text.replace(old, new, 1)


def _agent(text, tmp, name='probe'):
    p = os.path.join(tmp, '%s.toml' % name)
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return p


# --------------------------------------------------------------------------- declaration

def group_declaration(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-ag-')
    try:
        def load(text):
            return lambda: decl.load_agent(_agent(text, tmp))

        shipped = {}
        for n in SHIPPED:
            shipped[n] = decl.load_agent(os.path.join(PKG_ROOT, 'common', 'agents',
                                                      '%s.toml' % n))
        s.ok('DG-01', 'all four shipped agents load, each with a return schema and evals',
             sorted(shipped) == sorted(SHIPPED)
             and all(a.returns and a.evals for a in shipped.values()),
             repr({k: (len(v.returns), len(v.evals)) for k, v in shipped.items()}))

        s.ok('DG-02', 'every shipped agent is read-only and mints nothing',
             all(not a.writes for a in shipped.values())
             and all(not (set(a.tools) & decl.WRITING_TOOLS) for a in shipped.values()),
             'an agent that wrote cards would be a second minter of a prefix that has one')

        a = decl.load_agent(_agent(AGENT_OK, tmp))
        s.ok('DG-03', 'a well-formed agent loads and its accessors resolve',
             (a.name, a.title, a.return_kind) == ('probe', 'Probe', 'records')
             and a.field('band').values == ['high', 'low'] and a.field('nope') is None
             and len(a.evals) == 1 and a.evals[0].fails_when, repr(a.name))

        s.raises('DG-04', 'an agent with no `agent` key is refused by name',
                 load(_swap(AGENT_OK, 'agent     = "probe"', '')), 'no `agent` key')

        s.raises('DG-05', 'an agent name that is not lowercase kebab-case is refused',
                 load(_swap(AGENT_OK, '"probe"', '"Probe_One"')), 'lowercase kebab-case')

        s.raises('DG-06', 'an agent with no job is refused',
                 load(_swap(AGENT_OK, 'job       = "A fixture job, written long enough to clear '
                                      'the minimum length the loader imposes."', 'job = ""')),
                 'no `job`')

        s.raises('DG-07', 'a job too short to send anyone anywhere is refused, with its length',
                 load(_swap(AGENT_OK, 'A fixture job, written long enough to clear the minimum '
                                      'length the loader imposes.', 'Find things.')),
                 ('names a topic rather than a', 'characters'))

        s.raises('DG-08', 'an unknown model is refused and the known ones are listed',
                 load(_swap(AGENT_OK, 'model     = "inherit"', 'model = "gpt"')),
                 ('unknown model', 'Known:'))

        s.raises('DG-09', 'an agent declaring no tools is refused',
                 load(_swap(AGENT_OK, 'tools     = ["Read", "Grep"]', 'tools = []')),
                 'no `tools`')

        s.raises('DG-10', 'a read-only agent asking for a writing tool is refused structurally',
                 load(_swap(AGENT_OK, 'tools     = ["Read", "Grep"]',
                            'tools = ["Read", "Write"]')),
                 ('declares `writes = false` but asks for', 'Write'))

        s.accepts('DG-11', 'the same tool is accepted once the agent declares that it writes',
                  load(_swap(_swap(AGENT_OK, 'tools     = ["Read", "Grep"]',
                                   'tools = ["Read", "Write"]'),
                             'writes    = false', 'writes = true')))

        s.raises('DG-12', 'an unknown return kind is refused',
                 load(_swap(AGENT_OK, 'kind    = "records"', 'kind = "vibes"')),
                 'unknown return kind')

        s.raises('DG-13', 'an agent with no return fields is refused: prose cannot be checked',
                 load(AGENT_OK.split('[[returns.fields]]')[0]
                      + '\n[[evals]]\nid = "PB-1"\nasserts = "x"\nfails_when = "y"\n'),
                 'declares no fields')

        s.raises('DG-14', 'a return field declared twice is refused',
                 load(AGENT_OK + '\n[[returns.fields]]\nname = "band"\ntype = "scalar"\n'),
                 "return field 'band' declared twice")

        s.raises('DG-15', 'an unknown return field type is refused',
                 load(_swap(AGENT_OK, 'type     = "list<obj>"', 'type = "blob"')),
                 ('unknown type', 'Known:'))

        s.raises('DG-16', 'an enum return field with no values is refused',
                 load(_swap(AGENT_OK, 'values   = ["high", "low"]\n', '')),
                 'declares no values')

        s.raises('DG-17', 'a list of objects that names no keys is refused: it is not a schema',
                 load(_swap(AGENT_OK, 'of       = ["where", "quote"]\n', '')),
                 'names no keys in `of`')

        s.raises('DG-18', 'an underscore in a return field name is refused',
                 load(_swap(AGENT_OK, 'name     = "findings"', 'name = "the_findings"')),
                 'uses an underscore')

        s.raises('DG-19', 'an agent with no evals is refused, naming D1',
                 load(AGENT_OK.split('[[evals]]')[0]), ('no `[[evals]]`', 'D1'))

        s.raises('DG-20', 'an eval with no `fails_when` is refused: it would be a description',
                 load(_swap(AGENT_OK, 'fails_when = "It is not the case."\n', '')),
                 ('declares no `fails_when`', 'cannot fail is a'))

        s.raises('DG-21', 'an eval id used twice is refused',
                 load(AGENT_OK + '\n[[evals]]\nid = "PB-1"\nasserts = "x"\nfails_when = "y"\n'),
                 "eval id 'PB-1' used twice")

        s.raises('DG-22', 'an unknown key is refused wherever it appears, not silently ignored',
                 load(_swap(AGENT_OK, 'sent_when = "In a test."',
                            'sent_when = "In a test."\nwhenever = "always"')),
                 ('unknown key', 'read by nothing'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- emitter

def group_emitter(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-ae-')
    try:
        a = decl.load_agent(_agent(AGENT_OK, tmp))
        L = load_labels(PKG_ROOT, 'en')
        RU = load_labels(PKG_ROOT, 'ru')
        rt = EA.render_regions(a, L, 'a-vault', 'standard')

        s.eq('EA-01', 'render_regions produces exactly the four declared regions',
             tuple(sorted(rt)), tuple(sorted(EA.REGIONS)))

        s.ok('EA-02', 'the frontmatter carries the name, the tools and write:false',
             'name: probe' in rt['frontmatter']
             and 'tools: Read, Grep' in rt['frontmatter']
             and '  write: false' in rt['frontmatter']
             and 'induces: none' in rt['frontmatter'], repr(rt['frontmatter']))

        loud = decl.load_agent(_agent(_swap(AGENT_OK, 'model     = "inherit"',
                                           'model = "opus"'), tmp, 'loud'))
        s.ok('EA-03', 'model is projected only when it is not inherited',
             'model:' not in rt['frontmatter']
             and 'model: opus' in EA.frontmatter(loud, L, 'a-vault', 'standard'),
             'an inherited model written out is a decision the declaration did not make')

        light = EA.frontmatter(a, L, 'a-vault', 'light')
        s.ok('EA-04', 'the agent contract appears at standard and governed, not at light',
             'agent_contract:' in rt['frontmatter'] and 'agent_contract:' not in light,
             repr(light))

        rows = [ln for ln in rt['returns'].split('\n') if ln.startswith('| `')]
        s.eq('EA-05', 'the returns table carries one row per declared return field',
             len(rows), len(a.returns))

        s.ok('EA-06', 'an enum projects its values with the pipe escaped for the table cell, '
                      'and a list<obj> projects its keys',
             '`high` \\| `low`' in rt['returns']
             and '`where`' in rt['returns'] and '`quote`' in rt['returns'],
             'an unescaped pipe inside a cell splits the row, and escaping it twice renders '
             'the backslash: this asserts exactly one level')

        eval_rows = [ln for ln in rt['evals'].split('\n') if ln.startswith('| `')]
        s.ok('EA-07', 'every eval projects beside its own failure condition',
             len(eval_rows) == len(a.evals)
             and all(e.fails_when.rstrip('.') in rt['evals'] for e in a.evals)
             and all(e.id in rt['evals'] for e in a.evals),
             repr(rt['evals']))

        s.ok('EA-08', 'the job region carries the declared refusals and the induced failure mode',
             'Doing anything real.' in rt['job'] and 'the fixture' in rt['job'],
             repr(rt['job']))

        body = EA.skeleton(a, L, rt, src='abc123')
        found = regions.find_all(body)
        s.ok('EA-09', 'the skeleton is marker-bearing and every region round-trips',
             sorted(found) == sorted(EA.REGIONS)
             and all(found[r].verdict('abc123') == 'CLEAN' for r in EA.REGIONS),
             repr(sorted(found)))

        ok, n, advice = EA.check_size(body, a)
        over_ok, over_n, over_advice = EA.check_size('x\n' * 300, a)
        s.ok('EA-10', 'the projection is under the line cap, and going over is refused by name',
             ok and n <= EA.LINE_CAP and not over_ok and 'over the 200 cap' in over_advice
             and '.claude/agents/probe.md' in over_advice, repr((n, over_advice)))

        ru_regions = EA.render_regions(a, RU, 'a-vault', 'standard')
        ru_body = EA.skeleton(a, RU, ru_regions, src='abc123')
        s.ok('EA-11', 'the Russian labels reach the projection, headings and table alike',
             '## Задача' in ru_body and '## Проверки' in ru_body
             and '| Поле |' in ru_regions['returns'],
             'the label files are exercised nowhere else')

        s.ok('EA-12', 'nothing an agent projects carries an id or claims a folder',
             'id:' not in body and 'folder' not in body.lower()
             and 'mints: none' in body,
             'an agent that minted would be a second minter of a prefix that has one')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_declaration, group_emitter)
