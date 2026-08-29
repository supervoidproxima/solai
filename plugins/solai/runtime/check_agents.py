# -*- coding: utf-8 -*-
"""What holds about a place's agents and workflows, and what only a run could tell you.

    py check_agents.py <place-root> [--json]

Ships into a place beside the other checkers and reads that place's own compiled declarations,
never the package it was built from.

WHAT THIS CANNOT DO, said first because the verb's name overpromises. An eval here is a
statement about an agent's ANSWER - "a refutation rests on evidence stronger than inference" -
so executing one means sending the agent a real input and judging what comes back. That is a
model call. A deterministic script cannot make it, and a script that printed a score without
making it would be inventing the number.

So this checks what is checkable and says the rest is outstanding:

  AG-1  every declared agent carries at least one eval
  AG-2  every eval carries a `fails_when`, so it can fail
  AG-3  every agent declares a return schema with at least one required field
  AG-4  every projected agent file exists and its regions are stamped clean
  AG-5  no agent that declares `writes = false` asks for a writing tool
  WF-1  every workflow phase calls an agent this place actually has
  WF-2  every non-final phase declares what it carries
  WF-3  every barrier phase carries its justification
  WF-4  every projected script exists and holds no resume-breaking construct

Then it prints the eval roster as WORK OUTSTANDING, one line per eval, because the honest
report of an unexecuted check is its name and the word outstanding - not a blank, and not a
pass.
"""
import io
import json
import os
import re
import sys
import tomllib

sys.stdout.reconfigure(encoding='utf-8')

OS_AGENTS = '_system/os/agents'
OS_WORKFLOWS = '_system/os/workflows'
PROJ_AGENTS = '.claude/agents'
PROJ_WORKFLOWS = '.claude/workflows'

WRITING_TOOLS = {'Write', 'Edit', 'NotebookEdit'}
FORBIDDEN = ('Date.now', 'new Date', 'Math.random')
MARK = re.compile(r'(?m)^[ \t]*(?:#|//)?[ \t]*<!--[ \t]*solai:begin[ \t]+([A-Za-z0-9_-]+)'
                  r'(?:[ \t]+src=(\S*))?(?:[ \t]+body=(\S*))?[ \t]*-->[ \t]*$')


def _read(path):
    try:
        with io.open(path, encoding='utf-8') as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def _decls(root, rel):
    out = {}
    d = os.path.join(root, rel.replace('/', os.sep))
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith('.toml'):
            continue
        try:
            with open(os.path.join(d, f), 'rb') as fh:
                out[f[:-5]] = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            out[f[:-5]] = {'__error__': str(exc)}
    return out


def scan(root):
    findings, outstanding = [], []
    agents = _decls(root, OS_AGENTS)
    workflows = _decls(root, OS_WORKFLOWS)

    def fail(aid, subject, detail):
        findings.append({'id': aid, 'state': 'BLOCKER', 'subject': subject, 'detail': detail})

    for name, d in sorted(agents.items()):
        if '__error__' in d:
            fail('AG-0', name, 'the compiled declaration does not parse: %s' % d['__error__'])
            continue
        evals = d.get('evals') or []
        if not evals:
            fail('AG-1', name, 'declares no evals, so it asserts a capability with nothing '
                               'behind it (D1)')
        for e in evals:
            if not e.get('fails_when'):
                fail('AG-2', name, 'eval %r declares no fails_when, so it cannot fail and is a '
                                   'description' % e.get('id'))
            else:
                outstanding.append({'agent': name, 'id': e.get('id'),
                                    'asserts': e.get('asserts', ''),
                                    'fails_when': e.get('fails_when', '')})
        fields = (d.get('returns') or {}).get('fields') or []
        if not [f for f in fields if f.get('required')]:
            fail('AG-3', name, 'declares no required return field, so its answer has no shape '
                               'anything downstream can rely on')
        text = _read(os.path.join(root, PROJ_AGENTS.replace('/', os.sep), '%s.md' % name))
        if text is None:
            fail('AG-4', name, 'is declared but not projected into %s/' % PROJ_AGENTS)
        elif not MARK.search(text):
            fail('AG-4', name, 'is projected but carries no region markers, so nothing can tell '
                               'a hand edit from a regeneration')
        if not d.get('writes'):
            bad = sorted(set(d.get('tools') or []) & WRITING_TOOLS)
            if bad:
                fail('AG-5', name, 'declares writes = false but asks for %s' % ', '.join(bad))

    for name, w in sorted(workflows.items()):
        if '__error__' in w:
            fail('WF-0', name, 'the compiled declaration does not parse: %s' % w['__error__'])
            continue
        phases = w.get('phases') or []
        for i, p in enumerate(phases):
            last = (i == len(phases) - 1)
            if p.get('agent') not in agents:
                fail('WF-1', name, 'phase %r calls agent %r, which this place does not have'
                     % (p.get('title'), p.get('agent')))
            if not last and not p.get('carry'):
                fail('WF-2', name, 'phase %r declares no carry, so the next stage receives whole '
                                   'result objects' % p.get('title'))
            if p.get('shape') == 'barrier' and not p.get('barrier_because'):
                fail('WF-3', name, 'phase %r is a barrier and does not justify itself'
                     % p.get('title'))
        text = _read(os.path.join(root, PROJ_WORKFLOWS.replace('/', os.sep), '%s.js' % name))
        if text is None:
            fail('WF-4', name, 'is declared but not projected into %s/' % PROJ_WORKFLOWS)
        else:
            bad = [f for f in FORBIDDEN if f in text]
            if bad:
                fail('WF-4', name, 'the projected script contains %s, which breaks resume'
                     % ', '.join(bad))
    return {'agents': sorted(agents), 'workflows': sorted(workflows),
            'findings': findings, 'outstanding': outstanding}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = os.path.abspath(args[0]) if args else os.getcwd()
    r = scan(root)
    if '--json' in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1 if r['findings'] else 0

    print('agents: %d   workflows: %d   BLOCKER: %d'
          % (len(r['agents']), len(r['workflows']), len(r['findings'])))
    for f in r['findings']:
        print('  %-9s %-12s %s' % (f['id'], f['subject'], f['detail']))
    if not r['agents'] and not r['workflows']:
        print('  this place declares no agents and no workflows. Nothing to check, and that is a '
              'legitimate answer for a light place.')
        return 0
    if not r['findings']:
        print('  every declared agent and workflow holds together structurally.')

    print('\nevals: %d declared, %d executed, %d outstanding'
          % (len(r['outstanding']), 0, len(r['outstanding'])))
    print('  An eval judges an agent\'s answer, so running one needs a model call. This script '
          'makes none,')
    print('  and reports them as outstanding rather than printing a score it did not measure.')
    for e in r['outstanding']:
        print('  OUTSTANDING  %-10s %-6s %s' % (e['agent'], e['id'], e['asserts']))
    return 1 if r['findings'] else 0


if __name__ == '__main__':
    sys.exit(main())
