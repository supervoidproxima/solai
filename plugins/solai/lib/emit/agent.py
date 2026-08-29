# -*- coding: utf-8 -*-
"""An agent declaration into a working subagent definition in the vault's `.claude/agents/`.

The seventh emitter, and it changes nothing in the engine core: same four write modes, same
stamps, same plan table, same region merge. That was the test the design was there to pass.

Four regions are generated and belong to the engine. The rest is seeded once and belongs to
the user, for the same reason as the card skills: the parts that cannot be derived from a
declaration are exactly the parts worth writing by hand.

  generated: frontmatter, job, returns, evals
  seeded:    HOW TO SEND IT, NOTES

Why the return schema is projected as a table and not as prose: the agent's contract with its
caller is a shape, and a shape stated in prose is a shape two readers will disagree about. The
evals are projected with their `fails_when` beside them, because an eval whose failure
condition is kept somewhere else is one nobody checks.
"""
from . import cell, code, enum_list, table

REGIONS = ('frontmatter', 'job', 'returns', 'evals')
LINE_CAP = 200


# --------------------------------------------------------------------------- regions

def frontmatter(a, L, vault_name, tier):
    """Claude Code subagent frontmatter. `description` is what the router reads, so it carries
    the job in one sentence plus when to send it, and nothing decorative."""
    desc = a.job.strip().split('.')[0].strip().replace('"', "'")
    if a.sent_when:
        desc += '. Sent when: %s' % a.sent_when.rstrip('.').replace('"', "'")
    lines = [
        'name: %s' % a.name,
        'description: "%s. Returns %s; writes nothing."' % (desc, a.return_kind),
        'tools: %s' % ', '.join(a.tools),
    ]
    if a.model != 'inherit':
        lines.append('model: %s' % a.model)
    lines += [
        'scope: local',
        'permissions:',
        '  read: true',
        '  write: %s' % ('true' if a.writes else 'false'),
        '  execute: false',
        '  network: false',
    ]
    if tier in ('standard', 'governed'):
        lines += [
            'agent_contract:',
            '  contract_version: 1',
            '  vault: "%s"' % vault_name,
            '  returns: %s' % a.return_kind,
            '  mints: none',
            '  induces: %s' % a.induces,
        ]
    return '\n'.join(lines)


def job(a, L):
    out = [a.job.strip()]
    if a.reads:
        out += ['', '**%s**' % L('agent.reads'), '']
        out += ['- %s' % r for r in a.reads]
    if a.refusals:
        out += ['', '**%s**' % L('agent.refusals'), '']
        out += ['- %s' % r for r in a.refusals]
    if a.induces and a.induces != 'none':
        out += ['', '%s `%s`. %s' % (L('agent.induces'), a.induces,
                                     L('agent.induces-note'))]
    return '\n'.join(out)


def returns(a, L):
    rows = []
    for r in a.returns:
        detail = r.meaning.rstrip('.')
        if r.values:
            detail = '%s. %s' % (enum_list(r.values), detail)
        if r.of:
            detail = '%s %s. %s' % (L('agent.keys'), ', '.join(code(k) for k in r.of), detail)
        rows.append([code(r.name), code(r.type),
                     L('agent.yes') if r.required else L('agent.no'), detail + '.'])
    out = ['%s **%s**. %s' % (L('agent.kind'), a.return_kind, a.return_meaning.rstrip('.') + '.'),
           '',
           table([L('agent.field'), L('agent.type'), L('agent.required'),
                  L('agent.meaning')], rows),
           '',
           L('agent.returns-note')]
    return '\n'.join(out)


def evals(a, L):
    rows = [[code(e.id), e.asserts.rstrip('.') + '.', e.fails_when.rstrip('.') + '.']
            for e in a.evals]
    return '\n'.join([
        table([L('agent.eval'), L('agent.asserts'), L('agent.fails-when')], rows),
        '',
        L('agent.evals-note'),
    ])


# --------------------------------------------------------------------------- seeded

def seeded_body(a, L):
    """Written once, then the user's. An agent's calling convention is discovered by using it,
    and a generated guess at it would be rewritten on first contact."""
    return '\n\n'.join([
        '## %s' % L('agent.how-to-send'),
        L('agent.how-to-send-seed') % {'name': a.name, 'kind': a.return_kind},
        '## %s' % L('agent.notes'),
        L('agent.notes-seed'),
    ])


# --------------------------------------------------------------------------- assembly

def render_regions(a, L, vault_name, tier):
    return {
        'frontmatter': frontmatter(a, L, vault_name, tier),
        'job': job(a, L),
        'returns': returns(a, L),
        'evals': evals(a, L),
    }


def skeleton(a, L, regions_text, src='unstamped'):
    from .. import regions as R
    body = [('job', L('agent.job')),
            ('returns', L('agent.returns')),
            ('evals', L('agent.evals'))]
    out = ['---',
           R.render('frontmatter', regions_text['frontmatter'], src, comment='# '),
           '---',
           '',
           '=== %s ===' % a.title.upper(),
           '']
    for rid, title in body:
        out += ['## %s' % title, '', R.render(rid, regions_text[rid], src), '']
    out += [seeded_body(a, L), '']
    return '\n'.join(out)


def check_size(text, a):
    """-> (ok, lines, advice). Refuse before writing, and name what to move."""
    n = len(text.split('\n'))
    if n <= LINE_CAP:
        return True, n, ''
    biggest = 'the eval table' if len(a.evals) > 4 else 'the refusals'
    return False, n, ('.claude/agents/%s.md would be %d lines, over the %d cap. Move %s to '
                      '`.claude/agents/%s-evals.md` and reference it by path.'
                      % (a.name, n, LINE_CAP, biggest, a.name))
