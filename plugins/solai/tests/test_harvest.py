# -*- coding: utf-8 -*-
"""15 assertions on the harvest loop: what a vault changed, and which vaults went unread.

WHAT IS COVERED. The selection of divergent rows from a plan, the log's read and write, the
staleness rule the release prints from, and the two properties the feature exists for: that one
function renders every comparison, and that the reminder is a reminder rather than a gate.

WHAT IS NOT, said here rather than implied by silence. Nothing here runs `scaffold.py
--harvest` end to end against a real vault; that is `verify_engine.py`'s work and was done by
hand against the Counselor, which is where the first real divergence came from. And nothing
tests that a person runs it. That is the residue `CHG-020` named and cannot be tested away.
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
for p in (PKG, os.path.dirname(PKG)):
    if p not in sys.path:
        sys.path.insert(0, p)

from lib import fsplan, harvest as H                                 # noqa: E402

EXPECTED = 15
NAME = 'harvest'


def _act(rel, kind=fsplan.SKIP, verdict='LOCAL', content='src.py'):
    return fsplan.Action(kind, rel, 'scripts', content=content, verdict=verdict,
                         reason='edited here since we wrote it; keep yours with --adopt')


def group_selection(s):
    """What counts as something to carry up, and what does not."""
    rows = [_act('a.py', verdict='LOCAL'),
            _act('b.py', verdict='FOREIGN'),
            _act('c.py', verdict=H.SIGNED),
            _act('d.py', kind=fsplan.NOOP, verdict='CLEAN'),
            _act('e.py', kind=fsplan.COPY, verdict='UPDATED'),
            _act('f.py', verdict='FOREIGN', content=None)]
    unsigned, signed = H.divergences(rows)

    s.eq('HV-01', 'a copied file this vault changed is selected, whether the record calls it '
                  'LOCAL or FOREIGN',
         sorted(a.rel for a in unsigned), ['a.py', 'b.py'])

    s.eq('HV-02', 'a signed divergence is selected too, and kept apart: a signature names who '
                  'decided, not that there is nothing here to take',
         [a.rel for a in signed], ['c.py'])

    s.ok('HV-03', 'a file the package would write, or has just written, is not a divergence',
         all(a.rel not in ('d.py', 'e.py') for a in unsigned + signed),
         'NOOP and COPY rows are the package agreeing with the vault, or overwriting it')

    s.ok('HV-04', 'a skipped row with no source to compare against is left out: a generated '
                  'artefact has no shipped file, and a diff against nothing is not a finding',
         all(a.rel != 'f.py' for a in unsigned + signed),
         'this is the same limit --diff <path> refuses on, and harvest names it in its output')


def group_log(s):
    """The log is a record of harvests performed, never a census of vaults that exist."""
    tmp = tempfile.mkdtemp(prefix='solai-harvest-')
    try:
        path = os.path.join(tmp, 'private', 'harvested.json')

        s.eq('HV-05', 'a log that has never been written is empty rather than an error: '
                      'losing it costs a reminder, refusing to run would cost the run',
             H.read_log(path), {})

        os.makedirs(os.path.dirname(path))
        with io.open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json at all')
        s.eq('HV-06', 'a corrupt log is empty too, on the same reasoning', H.read_log(path), {})

        vault = os.path.join(tmp, 'vault')
        os.makedirs(vault)
        row = H.record(vault, '0.37.0', [_act('a.py')], [_act('c.py', verdict=H.SIGNED)],
                       path=path)
        log = H.read_log(path)
        s.ok('HV-07', 'a harvest writes down the vault, the version it was read at, and what '
                      'it held',
             list(log) == [os.path.abspath(vault)] and row['version'] == '0.37.0'
             and row['unsigned'] == 1 and row['signed'] == 1
             and row['files'] == ['a.py', 'c.py'], repr(log))

        H.record(vault, '0.38.0', [], [], path=path)
        log = H.read_log(path)
        s.ok('HV-08', 'harvesting the same vault again supersedes its row rather than '
                      'appending one: the question is when it was last read, not how often',
             len(log) == 1 and log[os.path.abspath(vault)]['version'] == '0.38.0',
             repr(log))

        other = os.path.join(tmp, 'other')
        os.makedirs(other)
        H.record(other, '0.38.0', [], [], path=path)
        s.eq('HV-09', 'a second vault is a second row', len(H.read_log(path)), 2)

        with io.open(path, encoding='utf-8') as fh:
            data = json.loads(fh.read())
        s.ok('HV-10', 'the log is keyed by absolute path, which is what a person types back '
                      'and what a later run can check still exists',
             all(os.path.isabs(k) for k in data['vaults']), repr(list(data['vaults'])))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_due(s):
    """What the release names, and what it deliberately cannot."""
    tmp = tempfile.mkdtemp(prefix='solai-due-')
    try:
        here = os.path.join(tmp, 'here')
        os.makedirs(here)
        gone = os.path.join(tmp, 'gone')

        log = {here: {'version': '0.30.0', 'date': '2026-09-01'}}
        s.ok('HV-11', 'a vault last read at an older version is named, with the version and '
                      'the date, because that is the whole signal',
             [v for v, _ in H.due(log, '0.37.0')] == [here]
             and '0.30.0' in H.due(log, '0.37.0')[0][1], repr(H.due(log, '0.37.0')))

        s.eq('HV-12', 'a vault read at the version about to ship is not named: there is '
                      'nothing new to carry up from it',
             H.due({here: {'version': '0.37.0', 'date': '2026-09-13'}}, '0.37.0'), [])

        rows = H.due({gone: {'version': '0.30.0', 'date': '2026-09-01'}}, '0.37.0')
        s.ok('HV-13', 'a vault this machine can no longer see is named as that rather than '
                      'dropped: a row that vanishes silently is how a list stops being trusted',
             len(rows) == 1 and 'cannot see it' in rows[0][1], repr(rows))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_wiring(s):
    """Two properties of the code itself, each guarding a mistake this package has made."""
    rel = io.open(os.path.join(PKG, 'skills', 'solai-release', 'release.py'),
                  encoding='utf-8').read()
    # The CALL, not the definition. Written as `rel.index('print_harvest()')` first, which
    # matched `def print_harvest():` on the line above and stayed green with the call deleted
    # altogether. An assertion that cannot fail is not an assertion.
    at = rel.find('\n    print_harvest()\n')
    gates_at = rel.index("print('gates, run now rather than earlier:')")
    s.ok('HV-14', 'the release names unharvested vaults before the gates run and never '
                  'refuses on them: the list cannot be complete, and a gate on an incomplete '
                  'list is one people learn to pass rather than to satisfy',
         0 <= at < gates_at and 'problems.append' not in rel[at:gates_at],
         'harvesting is what to do before cutting a release, not an obligation left by one')

    sc = io.open(os.path.join(PKG, 'skills', 'solai-scaffold', 'scaffold.py'),
                 encoding='utf-8').read()
    s.eq('HV-15', 'one file and every file are compared by the same function, so --diff and '
                  '--harvest cannot drift apart the way a signature written in one place and '
                  'checked in another did, twice, in one hour',
         sc.count('difflib.unified_diff(here.split'), 1)


GROUPS = (group_selection, group_log, group_due, group_wiring)
