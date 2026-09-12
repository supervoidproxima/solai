# -*- coding: utf-8 -*-
"""7 assertions on atomic change-number minting.

CN-05 is the one the whole script exists for, and it is the only assertion in this package that
would pass by luck if the implementation were wrong. Sixteen threads race for the same number
against a real filesystem. With a read-then-write implementation some of them collide and a
record is destroyed; with `O_CREAT | O_EXCL` none of them can, because the check and the claim
are one call.

The vault this is written from lost two records that way and recovered them from a session
transcript that happened to still be open. `CHG-118` there calls that luck rather than a
property of the system. This is the property.
"""
import io
import os
import shutil
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, 'runtime'))

import mint_change as MC                                            # noqa: E402

EXPECTED = 7
NAME = 'minting'

DATE = '2026-09-12'


def _vault(tmp, existing=(), folder='changes', answers=None):
    root = os.path.join(tmp, 'v')
    os.makedirs(os.path.join(root, folder), exist_ok=True)
    for name in existing:
        io.open(os.path.join(root, folder, name), 'w', encoding='utf-8').write('x')
    if answers is not None:
        os.makedirs(os.path.join(root, '_system', 'os'), exist_ok=True)
        io.open(os.path.join(root, '_system', 'os', 'answers.toml'), 'w',
                encoding='utf-8').write(answers)
    return root


def group_numbering(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-cn-')
    try:
        root = _vault(tmp, ['CHG-001.md', 'CHG-002.md'])
        cid, path = MC.mint(root, 'A third record', DATE)
        s.ok('CN-01', 'the next number follows the highest on disk, and the file exists on return',
             cid == 'CHG-003' and os.path.exists(path), repr(cid))

        s.ok('CN-02', 'the claimed file already carries its own id and title',
             'id: CHG-003' in io.open(path, encoding='utf-8').read()
             and 'A third record' in io.open(path, encoding='utf-8').read(), 'stub is written')

        holes = _vault(os.path.join(tmp, 'h'), ['CHG-001.md', 'CHG-005.md'])
        cid2, _ = MC.mint(holes, 'After a hole', DATE)
        s.eq('CN-03', 'a hole is never filled: numbering continues from the highest seen',
             cid2, 'CHG-006')

        # Its own fixture: CN-03 minted into `holes` and legitimately moved its highest.
        # Two files whose highest number is five is the whole distinction being asserted.
        counted = _vault(os.path.join(tmp, 'c'), ['CHG-001.md', 'CHG-005.md'])
        s.eq('CN-04', 'the highest is read by globbing names, not by counting files',
             MC.highest(os.path.join(counted, 'changes')), 5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_race(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-cn2-')
    try:
        root = _vault(tmp, ['CHG-001.md'])
        got, errors = [], []
        lock = threading.Lock()
        start = threading.Event()

        def worker(i):
            start.wait()
            try:
                cid, _ = MC.mint(root, 'Racer %d' % i, DATE)
                with lock:
                    got.append(cid)
            except Exception as e:                                  # noqa: BLE001
                with lock:
                    errors.append(repr(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()

        s.eq('CN-05', 'sixteen writers racing for the same number all get a different one',
             (len(got), len(set(got)), errors), (16, 16, []))

        on_disk = [f for f in os.listdir(os.path.join(root, 'changes')) if f.endswith('.md')]
        s.eq('CN-06', 'every claimed number is a file, so no record was written over another',
             len(on_disk), 17)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def group_folder(s):
    tmp = tempfile.mkdtemp(prefix='solai-test-cn3-')
    try:
        root = _vault(tmp, [], folder='_changes',
                      answers='archetype = "role"\nchanges_folder = "_changes"\n')
        cid, path = MC.mint(root, 'In a renamed folder', DATE)
        s.ok('CN-07', "the change folder is read from the vault's own answers, not assumed",
             cid == 'CHG-001' and os.path.basename(os.path.dirname(path)) == '_changes',
             repr(path))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


GROUPS = (group_numbering, group_race, group_folder)
