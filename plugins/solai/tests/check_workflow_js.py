# -*- coding: utf-8 -*-
"""Check a projected workflow script the way its runner treats it.

    python tests/check_workflow_js.py <place-root> [...]

Requires `node` on PATH; skips with a stated reason when it is absent, rather than passing
quietly. A check that silently does nothing is worse than one that is missing.

WHY THE FILE IS CHECKED IN TWO HALVES. The runner reads `export const meta` statically - it has
to, because the docs require a pure literal - and then runs the rest of the body in an async
context, which is why a top-level `return` and a bare `await` are legal there. So neither half
is valid on its own terms:

  - `node --check` on the whole file fails on the top-level `return`.
  - Wrapping the whole file in an async function fails on `export`, which cannot sit in one.

Checking it as one unit therefore always fails, and a checker that always fails teaches people
to ignore it. Each region is checked against the rules that actually apply to it: the meta
region as an ES module, and the script region inside an async function with the runtime globals
stubbed. The meta literal is then EVALUATED, so `phases` is confirmed to be real data rather
than something that merely parses.
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from lib import regions                                             # noqa: E402
from lib.emit import workflow as EW                                 # noqa: E402

STUBS = ('const agent=async()=>({}),parallel=async()=>[],pipeline=async()=>[],'
         'phase=()=>{},log=()=>{},workflow=async()=>({}),'
         'args={items:[]},budget={total:null,spent:()=>0,remaining:()=>0};')


def _node(args, cwd=None):
    try:
        p = subprocess.run(['node'] + args, capture_output=True, text=True, cwd=cwd,
                           encoding='utf-8', errors='replace')
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    except FileNotFoundError:
        return None, 'node is not on PATH'


def check_file(path, tmpdir):
    """-> list of problems. Empty means the projection is real, runnable JavaScript."""
    problems = []
    text = io.open(path, encoding='utf-8').read()
    name = os.path.basename(path)
    found = regions.find_all(text)

    for rid in EW.REGIONS:
        if rid not in found:
            problems.append('%s: no `%s` region, so the file is not a projection' % (name, rid))
    if problems:
        return problems

    bad = EW.forbidden_in(text)
    if bad:
        problems.append('%s: contains %s, which breaks resume: the second run would make a '
                        'different call sequence and the cached prefix would stop matching'
                        % (name, ', '.join(bad)))

    # 1 the meta region as an ES module, then evaluated
    meta_src = found['meta'].content
    probe = os.path.join(tmpdir, name.replace('.js', '') + '.meta.mjs')
    io.open(probe, 'w', encoding='utf-8', newline='\n').write(
        meta_src + '\nprocess.stdout.write(JSON.stringify(meta))\n')
    code, out = _node([probe])
    if code is None:
        return ['node is not on PATH: %s could not be checked' % name]
    if code != 0:
        problems.append('%s: the meta region is not valid ES module JavaScript:\n    %s'
                        % (name, out.strip().split('\n')[0]))
    else:
        try:
            meta = json.loads(out)
        except ValueError:
            problems.append('%s: the meta region did not evaluate to data' % name)
            meta = {}
        for key in ('name', 'description', 'phases'):
            if not meta.get(key):
                problems.append('%s: meta declares no %s' % (name, key))
        for i, ph in enumerate(meta.get('phases') or []):
            if not ph.get('title'):
                problems.append('%s: meta phase %d has no title' % (name, i + 1))

    # 2 the script region inside an async function, with the runtime stubbed
    probe = os.path.join(tmpdir, name.replace('.js', '') + '.body.mjs')
    io.open(probe, 'w', encoding='utf-8', newline='\n').write(
        '%s\nasync function body() {\n%s\n}\nexport default body\n'
        % (STUBS, found['script'].content))
    code, out = _node(['--check', probe])
    if code != 0:
        problems.append('%s: the script region is not valid inside an async body:\n    %s'
                        % (name, out.strip().split('\n')[0]))
    return problems


def main():
    roots = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not roots:
        print('usage: check_workflow_js.py <place-root> [...]')
        return 2
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix='solai-wfjs-')
    checked, problems = 0, []
    for root in roots:
        d = os.path.join(root, '.claude', 'workflows')
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith('.js'):
                continue
            checked += 1
            problems += check_file(os.path.join(d, f), tmpdir)
    print('workflow scripts checked: %d   problems: %d' % (checked, len(problems)))
    for p in problems:
        print('  %s' % p)
    if checked and not problems:
        print('  every projection is valid JavaScript with an evaluable meta literal.')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
