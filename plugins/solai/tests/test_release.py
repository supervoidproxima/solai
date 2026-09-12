# -*- coding: utf-8 -*-
"""6 assertions on the release gate.

WHAT IS COVERED. The preflight predicates, and the one property the script exists for: that the
gates are the last thing before the push, not a step that ran earlier.

WHAT IS NOT, said here rather than implied by silence. The push, the fast-forward and the tag
are not exercised: they act on a real remote, and a test that mocks git proves the mock. They
are covered by the refusals in front of them and by the fact that nothing reaches them until
every gate has just returned green.
"""
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, 'skills', 'solai-release'))

import release as RL                                                # noqa: E402

EXPECTED = 6
NAME = 'release'


def group_preflight(s):
    s.ok('RL-01', 'the changelog is required to claim the version being released',
         RL.changelog_claims(RL.VERSION) and not RL.changelog_claims('99.99.99'),
         'a release nobody wrote down cannot be read back')

    src = io.open(os.path.join(PKG, 'skills', 'solai-release', 'release.py'),
                  encoding='utf-8').read()
    gates_at = src.index('print(\'gates, run now rather than earlier:\')')
    push_at = src.index("for args in (('push', 'origin', branch)")
    pre_at = src.index('problems, facts = preflight()')
    s.ok('RL-02', 'the gates run after the preflight and before the first push',
         pre_at < gates_at < push_at,
         'the order is the feature: a tree that changes after a gate is a tree nobody tested')

    s.eq('RL-03', 'all three gates are wired, each with the phrase that means it passed',
         sorted(n for n, _, _ in RL.GATES), ['engine', 'install', 'package'])

    for name, script, _ in RL.GATES:
        if not os.path.exists(os.path.join(PKG, script)):
            s.ok('RL-04', 'every wired gate is a script that exists', False, name)
            break
    else:
        s.ok('RL-04', 'every wired gate is a script that exists', True,
             ', '.join(sc for _, sc, _ in RL.GATES))


def group_refusals(s):
    src = io.open(os.path.join(PKG, 'skills', 'solai-release', 'release.py'),
                  encoding='utf-8').read()

    wanted = ('uncommitted file', 'already exists', 'no CHANGELOG row claims',
              'not on this branch', 'nothing to release')
    missing = [w for w in wanted if w not in src]
    s.eq('RL-05', 'every refusal names itself rather than exiting on a number', missing, [])

    # The obligation the script cannot discharge must survive a successful run, or the release
    # reports done while the vault it belongs to still reads `0 sent`.
    tail = src[src.index("print('released %s.' % tag)"):]
    s.ok('RL-06', 'a successful release still prints the vault obligation it cannot discharge',
         'sent-on' in tail and 'NOT DONE YET' in tail,
         'green gates here say nothing about whether the vault records what left')


GROUPS = (group_preflight, group_refusals)
