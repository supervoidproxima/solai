# -*- coding: utf-8 -*-
"""What a vault changed in a file this package ships, and which vaults have not been read.

R-6, decided in `CHG-020` after the second instance in two days. The package's only feedback
path from a running vault ran through somebody remembering what they had improved, in which
vault, months ago. It failed twice: `GAP-013`'s fix lived correct in the Counselor for days
while the package shipped the defect to everyone including that vault, and reached the package
only because an upgrade overwrote the file and a count moved.

THIS DOES NOT DISCOVER VAULTS AND DOES NOT CLAIM TO. A registry of vault paths, hand-kept, is
the thing `RES-012` refused: a list whose staleness nothing detects. What is kept here is
narrower and is a log rather than a census - one row per harvest actually performed, written by
the act itself. Its staleness IS the signal: a vault last read at 0.30.0 is exactly what the
release should name. A vault this package was never told about cannot appear, and the release
says that in words rather than implying completeness.

THE ROWS IT SELECTS are copied files: the package ships them, the vault runs them, and a
divergence is therefore about code this package owns. A generated artefact is the vault's own
judgement and has no shipped file to compare against, which is why `--diff <path>` refuses one.

SIGNED AND UNSIGNED ARE BOTH REPORTED, and the distinction between them is the open question
this closes. A signature under `--adopt <path>` says somebody decided and named the record;
it does not say the divergence holds nothing worth taking, and the Counselor's `stamp_check.py`
is the case in point, carrying a check the package has never had. So a signed row is listed
with its change record and diffed on request, and an unsigned one is diffed by default, because
nobody has accounted for it yet and that is the whole of what distinguishes the two.

The log lives outside the package's tracked files. It names real paths on one machine, and this
repository is public.
"""
import json
import os
import time

from . import fsplan

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                # .../plugins/solai
REPO = os.path.dirname(os.path.dirname(PKG))               # the repository root

LOG = os.path.join(REPO, 'private', 'harvested.json')

SIGNED = 'ADOPTED'
UNSIGNED = ('LOCAL', 'FOREIGN')


def divergences(actions):
    """-> (unsigned, signed). Every copied file this vault has changed, in plan order.

    The plan row is the authority on the state of a file, so this reads it rather than
    classifying anything a second time. A second classifier is how the engine grew two answers
    to one question twice, and it is how a signature was written that never matched.
    """
    unsigned, signed = [], []
    for a in actions:
        if a.kind != fsplan.SKIP or not a.content:
            continue
        if a.verdict in UNSIGNED:
            unsigned.append(a)
        elif a.verdict == SIGNED:
            signed.append(a)
    return unsigned, signed


def read_log(path=LOG):
    """-> {vault path: row}. A missing or unreadable log is empty, never an error.

    Losing this file costs a reminder. Refusing to run without it would cost the run.
    """
    text = fsplan.read(path)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    got = data.get('vaults')
    return got if isinstance(got, dict) else {}


def record(root, version, unsigned, signed, path=LOG):
    """Write down that this vault was read at this version, and what it held. -> the row.

    Keyed by absolute path, because that is what the person types and what the next run can
    check still exists. Rewritten whole: one row per vault, and the previous harvest of the
    same vault is superseded rather than accumulated.
    """
    log = read_log(path)
    row = {'version': version, 'date': time.strftime('%Y-%m-%d'),
           'unsigned': len(unsigned), 'signed': len(signed),
           'files': sorted(a.rel for a in list(unsigned) + list(signed))}
    log[os.path.abspath(root)] = row
    d = os.path.dirname(path)
    if d and not os.path.isdir(fsplan.w(d)):
        os.makedirs(fsplan.w(d))
    with open(fsplan.w(path), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps({'vaults': log}, ensure_ascii=False, indent=2) + '\n')
    return row


def due(log, version):
    """-> [(vault, why)] for every vault this package has read and has since moved past.

    A vault read at the version about to ship is not named: there is nothing new to carry up
    from it. A vault whose directory has gone is named as that, rather than dropped, because a
    row that vanishes silently is how a list stops being trusted.
    """
    out = []
    for vault in sorted(log):
        row = log[vault] or {}
        was = row.get('version') or 'an unrecorded version'
        if not fsplan.exists(vault):
            out.append((vault, 'last read at %s, and this machine cannot see it any more'
                        % was))
        elif was != version:
            out.append((vault, 'last read at %s, on %s' % (was, row.get('date') or 'no date')))
    return out
