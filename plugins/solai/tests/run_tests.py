# -*- coding: utf-8 -*-
"""The whole suite, one command:

    python tests/run_tests.py            (from ~/.claude/solai/plugins/solai)

Exits 0 only when every assertion passed AND the number that ran equals the number declared.
The second condition is the one that matters over time: a deleted assertion is a silently
weakened gate, so the runner treats one short of the declared total as red, exactly like a
failure.

No arguments, no discovery magic, no third-party runner. A gate that needs a flag to be green
is a gate somebody eventually runs with the flag.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
for p in (PKG, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from harness import Suite                                           # noqa: E402
import test_agents                                                  # noqa: E402
import test_args                                                    # noqa: E402
import test_authoring                                               # noqa: E402
import test_change                                                  # noqa: E402
import test_compiled
import test_harvest                                                 # noqa: E402
import test_decl                                                    # noqa: E402
import test_kb                                                      # noqa: E402
import test_primitives                                              # noqa: E402
import test_release                                                 # noqa: E402
import test_sensitive                                               # noqa: E402
import test_ui                                                      # noqa: E402
import test_wikilink                                                # noqa: E402
import test_workflows                                               # noqa: E402

MODULES = (test_primitives, test_decl, test_compiled, test_agents, test_workflows,
           test_authoring, test_ui, test_kb, test_sensitive, test_change, test_release,
           test_args, test_wikilink, test_harvest)


def main():
    suites, bodies = [], []
    for mod in MODULES:
        suite = Suite(mod.NAME, mod.EXPECTED)
        for group in mod.GROUPS:
            suite.group(group)
        suites.append(suite)

    print('')
    for suite in suites:
        head, body = suite.report()
        print('  %s' % head)
        if body:
            bodies.append(body)

    ran = sum(s.ran for s in suites)
    passed = sum(s.passed for s in suites)
    expected = sum(s.expected for s in suites)
    green = all(s.green() for s in suites)

    print('')
    if bodies:
        print('\n'.join(bodies))
        print('')
    print('  %d/%d assertions passed  (%d declared)' % (passed, ran, expected))
    print('  %s' % ('GREEN' if green else 'RED'))
    print('')
    return 0 if green else 1


if __name__ == '__main__':
    sys.exit(main())
