# -*- coding: utf-8 -*-
"""Prove a projected workflow can resume from a killed run, without needing a live runner.

    python tests/check_workflow_resume.py <place-root> [...]

WHAT RESUME ACTUALLY REQUIRES. A runner resumes by replaying the script and reusing the cached
result of every agent call whose (prompt, options) pair is unchanged; the first call that differs
and everything after it runs live. So resume works exactly as far as the script produces the SAME
CALL SEQUENCE on the second run, and no further. Wall-clock, randomness or set iteration order
anywhere in the script silently shortens the reusable prefix to nothing.

That property is checkable here, offline, with no model call:

  1. Run the script body in node with the runtime stubbed and every agent call recorded.
  2. Run it again. The two recordings must be byte-identical.
  3. Run it a third time with a stub that THROWS at call N - a killed run - keep the prefix it
     managed, then compare that prefix against the full recording. Every call before the kill
     must match, which is precisely the cached prefix a resume would reuse.

WHAT THIS DOES NOT PROVE. It does not exercise a real runner's cache, and it does not make a
model call: the stub returns schema-shaped placeholder data. A live end-to-end run remains
outstanding and is recorded as such rather than implied - the difference between "the script is
resumable" and "a resume was observed" is exactly the sort of gap this package refuses to leave
undeclared.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from lib import regions                                             # noqa: E402
from lib.emit import workflow as EW                                 # noqa: E402

# The stubbed runtime. `pipeline` and `parallel` keep their real ORDERING semantics, because
# ordering is the whole property under test; they do not need real concurrency to do that.
HARNESS = r'''
const CALLS = []
let budgetKill = KILLAT

function fromSchema(schema, seed) {
  if (!schema || !schema.properties) return {}
  const out = {}
  for (const key of Object.keys(schema.properties).sort()) {
    const p = schema.properties[key]
    if (p.type === 'array') {
      const item = {}
      for (const k of (p.items && p.items.required) || []) item[k] = k + '-' + seed
      out[key] = p.items && p.items.properties ? [item] : ['s-' + seed]
    } else if (p.type === 'boolean') out[key] = false
    else if (p.type === 'integer') out[key] = 0
    else if (p.enum) out[key] = p.enum[0]
    else out[key] = key + '-' + seed
  }
  return out
}

async function agent(prompt, opts) {
  opts = opts || {}
  CALLS.push({n: CALLS.length + 1, label: opts.label, phase: opts.phase,
              prompt: String(prompt).slice(0, 160),
              schemaKeys: opts.schema && opts.schema.properties
                ? Object.keys(opts.schema.properties).sort() : []})
  if (budgetKill > 0 && CALLS.length >= budgetKill) {
    throw new Error('KILLED at call ' + CALLS.length)
  }
  return fromSchema(opts.schema, CALLS.length)
}

async function parallel(thunks) {
  const out = []
  for (const t of thunks) out.push(await t())
  return out
}

async function pipeline(items, ...stages) {
  const out = []
  for (let i = 0; i < items.length; i++) {
    let v = items[i]
    for (const st of stages) v = await st(v, items[i], i)
    out.push(v)
  }
  return out
}

const phase = () => {}
const log = () => {}
const args = {items: ['alpha', 'beta', 'gamma']}
const budget = {total: null, spent: () => 0, remaining: () => 0}

async function body() {
BODY
}

body().then(
  () => process.stdout.write(JSON.stringify(CALLS)),
  (e) => process.stdout.write(JSON.stringify({killed: String(e.message), calls: CALLS}))
)
'''


def _run(body, killat, tmpdir, tag):
    src = HARNESS.replace('KILLAT', str(killat)).replace('BODY', body)
    p = os.path.join(tmpdir, '%s.mjs' % tag)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(src)
    try:
        r = subprocess.run(['node', p], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
    except FileNotFoundError:
        return None, 'node is not on PATH'
    if r.returncode != 0 and not r.stdout.strip():
        return None, (r.stderr or '').strip().split('\n')[0]
    try:
        return json.loads(r.stdout), None
    except ValueError:
        return None, 'the run produced no call log: %s' % (r.stdout or r.stderr)[:200]


def check_file(path, tmpdir):
    problems, name = [], os.path.basename(path)
    text = io.open(path, encoding='utf-8').read()
    found = regions.find_all(text)
    if 'script' not in found:
        return ['%s: no `script` region' % name], None
    body = found['script'].content
    tag = name.replace('.js', '')

    first, err = _run(body, 0, tmpdir, tag + '-1')
    if err:
        return ['%s: could not run: %s' % (name, err)], None
    second, err = _run(body, 0, tmpdir, tag + '-2')
    if err:
        return ['%s: could not re-run: %s' % (name, err)], None

    if json.dumps(first) != json.dumps(second):
        problems.append('%s: two runs of the same script produced DIFFERENT call sequences, so a '
                        'resume would reuse nothing' % name)
    if not first:
        problems.append('%s: the script made no agent calls at all' % name)
        return problems, None

    killat = max(2, len(first) // 2)
    killed, err = _run(body, killat, tmpdir, tag + '-k')
    if err:
        return problems + ['%s: could not run the killed pass: %s' % (name, err)], None
    prefix = (killed or {}).get('calls') or []
    if not (killed or {}).get('killed'):
        problems.append('%s: the killed pass did not stop, so nothing was proven about resume'
                        % name)
    elif len(prefix) != killat:
        problems.append('%s: killed after %d calls but recorded %d'
                        % (name, killat, len(prefix)))
    elif json.dumps(prefix) != json.dumps(first[:len(prefix)]):
        problems.append('%s: the killed run\'s first %d calls differ from the full run\'s, so the '
                        'cached prefix a resume relies on would not match'
                        % (name, len(prefix)))
    return problems, {'calls': len(first), 'resumable_prefix': len(prefix),
                      'phases': sorted({c['phase'] for c in first if c.get('phase')})}


def main():
    roots = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not roots:
        print('usage: check_workflow_resume.py <place-root> [...]')
        return 2
    tmpdir = tempfile.mkdtemp(prefix='solai-wfres-')
    checked, problems = 0, []
    for root in roots:
        d = os.path.join(root, '.claude', 'workflows')
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith('.js'):
                continue
            checked += 1
            probs, info = check_file(os.path.join(d, f), tmpdir)
            problems += probs
            if info and not probs:
                print('  %-14s %d calls   identical on re-run   resumed from call %d   phases %s'
                      % (f, info['calls'], info['resumable_prefix'], ', '.join(info['phases'])))
    print('workflow scripts replayed: %d   problems: %d' % (checked, len(problems)))
    for p in problems:
        print('  %s' % p)
    if checked and not problems:
        print('  every script replays identically and its killed prefix matches.')
        print('  NOT proven here: a live runner cache, and any real model call.')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
