# -*- coding: utf-8 -*-
"""A workflow declaration into a runnable, resumable script in the place's `.claude/workflows/`.

The eighth emitter. The declaration names the phases and which agent each one calls; this
renders the script. The script is a PROJECTION, so it is regenerated and never hand-edited -
same rule as every other artefact here, and the reason it is stamped.

WHY THE SCRIPT IS THE ARTEFACT AND NOT A PROSE RUNBOOK. Resume is the whole point. A run that
dies halfway has to continue from where it stopped rather than from the beginning, and that
requires the steps to be replayable in the same order with the same inputs - which a script has
and a paragraph of instructions does not.

WHAT RESUMABILITY ACTUALLY DEPENDS ON, and therefore what this emitter guarantees:

  - No wall-clock and no randomness. `Date.now()`, `new Date()` and `Math.random()` make the
    same script produce a different call sequence on the second run, so the cached prefix stops
    matching and resume degrades into a full re-run. This emitter never writes them, and
    `test_workflows.py` asserts their absence in every projection.
  - Stable call ORDER. The phases are emitted in declared order and the items in each phase come
    from `args` in the order given, so an interrupted run replays identically up to the point it
    stopped.
  - A schema on every agent call. The schema comes from the agent's own return declaration, so a
    resumed run validates its cached results against the same shape the first run did.

The return schema is the payoff of declaring one: a JSON Schema is generated from the agent's
`[returns]` block, which is what forces structured output instead of prose at the one boundary
where prose would be unrecoverable.

DECLARED UNCERTAINTY: the stamp markers are JS line comments above `export const meta`, so the
file's first token is a comment rather than the export. That is ordinary JavaScript and matches
how every other projection in this package carries its provenance, but the workflow runner's own
requirement is written as "must begin with export const meta". If a runner rejects it, the fix is
to move the markers below the meta block, not to drop the stamp.
"""
import json

REGIONS = ('meta', 'script')
LINE_CAP = 200

# The constructs that break resume. Asserted absent by the tests rather than trusted.
FORBIDDEN = ('Date.now', 'new Date', 'Math.random')


# --------------------------------------------------------------------------- schema

def schema_for(agent):
    """An agent's `[returns]` block as a JSON Schema, for the runner to enforce."""
    props, required = {}, []
    for r in agent.returns:
        node = {'description': r.meaning.strip()}
        if r.type == 'scalar':
            node['type'] = 'string'
        elif r.type == 'int':
            node['type'] = 'integer'
        elif r.type == 'bool':
            node['type'] = 'boolean'
        elif r.type == 'enum':
            node['type'] = 'string'
            node['enum'] = list(r.values)
        elif r.type == 'list<str>':
            node['type'] = 'array'
            node['items'] = {'type': 'string'}
        elif r.type == 'list<obj>':
            node['type'] = 'array'
            node['items'] = {
                'type': 'object',
                'properties': {k: {'type': 'string'} for k in r.of},
                'required': list(r.of),
            }
        props[r.name] = node
        if r.required:
            required.append(r.name)
    return {'type': 'object', 'properties': props, 'required': required}


def _js(value, indent=0):
    """JSON is valid JS for these shapes, and `json.dumps` is deterministic with sort_keys."""
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    pad = ' ' * indent
    return ('\n' + pad).join(text.split('\n'))


def _q(text):
    """A single-quoted JS string. Newlines are refused rather than escaped: every string here
    comes from a declaration field that is a single line by construction."""
    return "'%s'" % str(text).replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ')


# --------------------------------------------------------------------------- regions

def meta_region(w):
    """`export const meta` must be a PURE literal - no variables, no interpolation - so it is
    rendered as one, from the declaration, with a phase entry per declared phase."""
    phases = [{'title': p.title, 'detail': p.detail or p.over} for p in w.phases]
    lines = [
        'export const meta = {',
        '  name: %s,' % _q(w.name),
        '  description: %s,' % _q(w.goal.strip().replace('\n', ' ')),
        '  whenToUse: %s,' % _q(w.run_when or w.input),
        '  phases: %s,' % _js(phases, 2),
        '}',
    ]
    return '\n'.join(lines)


def _schema_consts(w, agents):
    out = []
    for name in w.agents:
        a = agents.get(name)
        if a is None:
            continue
        out.append('const %s_RETURNS = %s' % (name.upper().replace('-', '_'),
                                              _js(schema_for(a), 0)))
    return '\n\n'.join(out)


def _stage(w, p, agents, first, src):
    """One phase as a JS statement. A pipeline maps over its items; a barrier collects them."""
    a = agents.get(p.agent)
    const = '%s_RETURNS' % p.agent.upper().replace('-', '_')
    job = (a.job.strip().split('.')[0] if a else p.detail).replace('\n', ' ')
    lines = ['phase(%s)' % _q(p.title)]
    if p.is_barrier:
        lines += [
            '// Barrier, and the declaration says why: %s' % p.barrier_because.strip().split('.')[0],
            'const %s = await parallel([() => agent(' % _var(p),
            '  %s +' % _q('%s. Consider these together, not one at a time: ' % job),
            '  JSON.stringify(%s),' % src,
            '  {label: %s, phase: %s, schema: %s})])' % (_q('%s:all' % p.agent),
                                                         _q(p.title), const),
        ]
    else:
        lines += [
            'const %s = await pipeline(%s,' % (_var(p), src),
            '  (item, original, i) => agent(',
            '    %s + asText(original ?? item),' % _q('%s. Work on: ' % job),
            '    {label: %s + i, phase: %s, schema: %s}))'
            % (_q('%s:' % p.agent), _q(p.title), const),
        ]
    return '\n'.join(lines)


def _var(p):
    return 'phase%s' % (p.n if p.n else 1)


def script_region(w, agents):
    """The body: schemas, then one statement per phase, then the return."""
    parts = [_schema_consts(w, agents), '']
    parts.append('// %s' % w.goal.strip().replace('\n' , ' '))
    parts.append('// Input: %s' % w.input)
    parts.append('// Output: %s' % w.output)
    parts.append('')
    parts.append('if (!args || !Array.isArray(args.items)) {')
    parts.append('  throw new Error(%s)' % _q(
        'this workflow needs args.items: %s' % w.input))
    parts.append('}')
    parts.append('log(%s + args.items.length)' % _q('%s over ' % w.title))
    parts.append('')
    # An object interpolated into a prompt with String() arrives as "[object Object]". Every
    # non-first stage receives records, so the conversion is explicit and lossless.
    parts.append('const asText = (x) => typeof x === %s ? x : JSON.stringify(x)'
                 % _q('string'))
    parts.append('')
    src, carried = 'args.items', None
    for i, p in enumerate(w.phases):
        parts.append(_stage(w, p, agents, first=(i == 0), src=src))
        parts.append('')
        carried = _var(p)
        if i + 1 < len(w.phases):
            # The carry is declared, so the chain is explicit and correct for any phase count.
            nxt = 'carry%d' % (p.n or i + 1)
            parts.append('const %s = %s.flat().filter(Boolean)%s'
                         % (nxt, carried,
                            ('.flatMap((r) => r[%s] ?? [])' % _q(p.carry)) if p.carry else ''))
            parts.append('')
            src = nxt
    parts.append('return {')
    parts.append('  workflow: %s,' % _q(w.name))
    parts.append('  phases: %s,' % _js([p.title for p in w.phases], 2))
    parts.append('  result: %s.flat().filter(Boolean),' % carried)
    parts.append('  counted: %s.flat().filter(Boolean).length,' % carried)
    parts.append('}')
    return '\n'.join(parts)


# --------------------------------------------------------------------------- assembly

def render_regions(w, agents):
    return {'meta': meta_region(w), 'script': script_region(w, agents)}


def skeleton(w, agents, regions_text, src='unstamped'):
    from .. import regions as R
    return '\n'.join([
        R.render('meta', regions_text['meta'], src, comment='// '),
        '',
        R.render('script', regions_text['script'], src, comment='// '),
        '',
    ])


def check_size(text, w):
    n = len(text.split('\n'))
    if n <= LINE_CAP:
        return True, n, ''
    return False, n, ('.claude/workflows/%s.js would be %d lines, over the %d cap. Most of the '
                      'length is the inlined return schemas, which cannot move: a workflow script '
                      'has no filesystem access, so the schema has to travel with it. Split the '
                      'workflow at the phase that changes subject, or call fewer agents.'
                      % (w.name, n, LINE_CAP))


def forbidden_in(text):
    """-> the resume-breaking constructs present. Empty is the only acceptable answer."""
    return [f for f in FORBIDDEN if f in text]
