# -*- coding: utf-8 -*-
"""The end-to-end verification, as a command:

    python tests/verify_engine.py     (from ~/.claude/solai/plugins/solai)

For each of the four archetypes: load the declarations, scaffold into a fresh temp directory
with `--apply`, re-run `--plan` and require it to be ENTIRELY NOOP, then run `validate_cards`,
`stamp_check` and `check_links` against the result. `personal` is built with
`output_language=ru`, because the label files are exercised nowhere else.

This existed only as a paragraph of prose in a handoff note, which meant the engine's pass
state rested on someone's word about a run nobody could repeat. The unit suite
(`run_tests.py`) proves the primitives; this proves the thing they add up to. Run both after
any engine change.

It also PROBES the checker: after everything reads clean, one generated region is edited and
the stamp check must name it. An all-clean report proves the checker ran, not that it works -
a checker that opened no files reports exactly the same thing, which is what a wholesale
skip of `.claude/` was hiding until 0.5.0.

ON THE EXPECTED NOOP COUNTS. The handoff note of 2026-08-27 records 6 / 25 / 25 / 21 against
an engine with no agents. Plan rows were 5 / 24 / 24 / 20 then: the difference is
`dashboard.html`, declared as an artefact in all four manifests but never planned, because it
reflects the vault AFTER the apply and is written by a post-apply subprocess. So the note
counted generated FILES and this gate counts PLAN ROWS. Both were right about the engine;
only the unit was ambiguous, and the plan-row count is the one used here because "the second
plan is entirely NOOP" is a statement about a plan.

At 0.5.0 the agent layer added two rows per agent - the projection and the compiled
declaration. At 0.6.0 the workflow layer does the same per workflow, giving 5 / 38 / 28 / 32.

The `role` figure moved 34 -> 36 when the `reader` agent was added to that archetype: the
documents constituting a role arrive as Word, Excel and PDF, and neither scout nor extractor
can get words out of a deck. The declaration shipped and this table did not follow it, so the
gate had been reporting a failure of its own bookkeeping as a failure of the engine.

The three card archetypes moved again, by two each, when `check_binaries.py` and
`measure_cards.py` joined the copied runtime: one plan row per copied file. `minimal`
takes neither - it declares no class, so there are no cards to measure and nothing for
the attachment conventions to be declared against.

`role` then went 38 -> 36: `decision` is no longer scaffolded, so its compiled declaration
and its card skill are not written. The declaration still ships and is still installable;
it is the building of it by default that stopped.

Two extra checkers run against any place that carries workflows: `check_workflow_js.py` proves
each projection is real JavaScript with an evaluable `meta` literal, and
`check_workflow_resume.py` replays each script twice with the runtime stubbed and demands an
identical call sequence, then kills a run mid-way and demands the surviving prefix match. That
is the property a resume actually depends on. A live runner cache and a real model call remain
unexercised, and are stated as such rather than implied.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SCAFFOLD = os.path.join(PKG, 'skills', 'solai-scaffold', 'scaffold.py')

# archetype, output language, expected NOOP plan rows, agents projected, workflows projected.
# Each agent and each workflow contributes two rows: the projection under `.claude/` and its
# declaration compiled into `_system/os/`.
# Gates a correctly built, empty place is SUPPOSED to raise. A gate is not an invalidity:
# `validate_cards.py` exits non-zero on BLOCKER alone, and AV-2 says of itself that it "is
# reported every run until it is not true". Demanding zero gates from a place that has by
# construction shipped nothing is a category error, and it is why this file had been red:
# three of the four archetypes failed on the one gate they are built to raise.
FRESH_GATES = {'AV-3'}

CASES = (
    ('minimal', 'en', 6, 0, 0),
    ('project', 'en', 44, 5, 3),
    ('personal', 'ru', 32, 2, 0),
    ('role', 'en', 36, 5, 2),
)

ANSWERS = ('remit=A throwaway place built only to verify the engine.',
           'first_artefact=One verification report that leaves this place.')


def run(args, cwd=None):
    p = subprocess.run([sys.executable] + [str(a) for a in args], cwd=cwd,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def num(pattern, text, default=None):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


def main():
    tmp = tempfile.mkdtemp(prefix='solai-verify-')
    rows, failures = [], []
    try:
        for arch, lang, expect_noop, expect_agents, expect_wf in CASES:
            root = os.path.join(tmp, arch)
            os.makedirs(root)
            answers = ['archetype=%s' % arch, 'name=verify-%s' % arch,
                       'output_language=%s' % lang] + list(ANSWERS)
            base = [SCAFFOLD, root, '--archetype', arch, '--answers'] + answers

            code, out = run(base + ['--apply'])
            if code != 0:
                failures.append('%s: apply exited %d' % (arch, code))
                rows.append((arch, lang, 'APPLY FAILED', out[-800:]))
                continue

            code, out2 = run(base)
            # The summary line is indented, so the anchor needs multiline mode. Without it the
            # count silently reads 0 and every archetype fails for the wrong reason.
            noop = num(r'(?m)^\s*NOOP (\d+)\s*$', out2, 0)
            others = [k for k in ('WRITE', 'SKIP', 'COPY')
                      if re.search(r'\b%s \d+\b' % k, out2.split('  NOOP')[-1])]
            entirely_noop = not [ln for ln in out2.split('\n')
                                 if re.match(r'^\s+(WRITE|SKIP|COPY)\s', ln)]
            if noop != expect_noop:
                failures.append('%s: NOOP %d, expected %d' % (arch, noop, expect_noop))
            if not entirely_noop:
                failures.append('%s: the second plan is not entirely NOOP (%s)'
                                % (arch, ', '.join(others)))

            projected = os.path.join(root, '.claude', 'agents')
            compiled = os.path.join(root, '_system', 'os', 'agents')
            got = sorted(f for f in os.listdir(projected)) if os.path.isdir(projected) else []
            got_decl = sorted(os.listdir(compiled)) if os.path.isdir(compiled) else []
            if len(got) != expect_agents or len(got_decl) != expect_agents:
                failures.append('%s: %d agents projected and %d declarations compiled, '
                                'expected %d of each' % (arch, len(got), len(got_decl),
                                                         expect_agents))

            wf_dir = os.path.join(root, '.claude', 'workflows')
            wf_decl = os.path.join(root, '_system', 'os', 'workflows')
            got_wf = sorted(os.listdir(wf_dir)) if os.path.isdir(wf_dir) else []
            got_wf_decl = sorted(os.listdir(wf_decl)) if os.path.isdir(wf_decl) else []
            if len(got_wf) != expect_wf or len(got_wf_decl) != expect_wf:
                failures.append('%s: %d workflows projected and %d declarations compiled, '
                                'expected %d of each' % (arch, len(got_wf), len(got_wf_decl),
                                                         expect_wf))

            checks = []
            for script in ('validate_cards.py', 'stamp_check.py', 'check_links.py',
                           'check_agents.py'):
                p = os.path.join(root, '_system', 'scripts', script)
                if not os.path.exists(p):
                    continue
                _, o = run([p, root])
                if script == 'validate_cards.py':
                    b, g = num(r'BLOCKER (\d+)', o, -1), num(r'GATE (\d+)', o, -1)
                    gate_ids = set(re.findall(r'(?m)^\s+GATE\s+(\S+)', o))
                    checks.append('BLOCKER %s GATE %s%s'
                                  % (b, g, ' (%s)' % ', '.join(sorted(gate_ids))
                                     if gate_ids else ''))
                    if b != 0:
                        failures.append('%s: %d BLOCKER' % (arch, b))
                    unexpected = gate_ids - FRESH_GATES
                    if unexpected:
                        failures.append('%s: unexpected gate %s on a freshly built place'
                                        % (arch, ', '.join(sorted(unexpected))))
                elif script == 'stamp_check.py':
                    st = num(r'stamped files: (\d+)', o, -1)
                    cl = num(r'clean: (\d+)', o, -1)
                    he = num(r'hand-edited: (\d+)', o, -1)
                    checks.append('stamped %s clean %s' % (st, cl))
                    if st != cl or he != 0:
                        failures.append('%s: %d stamped but %d clean, %d hand-edited'
                                        % (arch, st, cl, he))
                elif script == 'check_links.py':
                    br = num(r'broken links (\d+)', o, -1)
                    checks.append('broken links %s' % br)
                    if br != 0:
                        failures.append('%s: %d broken links' % (arch, br))
                else:
                    ag = num(r'agents: (\d+)', o, -1)
                    bl = num(r'BLOCKER: (\d+)', o, -1)
                    ev = num(r'evals: (\d+) declared', o, 0)
                    checks.append('agents %s evals %s outstanding' % (ag, ev))
                    if bl != 0:
                        failures.append('%s: check_agents reported %d BLOCKER' % (arch, bl))
            # The projected scripts are checked as real JavaScript, and replayed to prove the
            # call sequence a resume would reuse is stable. Both live beside this file.
            if got_wf:
                for tool, label in (('check_workflow_js.py', 'js'),
                                    ('check_workflow_resume.py', 'replay')):
                    code, o = run([os.path.join(HERE, tool), root])
                    checks.append('%s %s' % (label, 'ok' if code == 0 else 'FAILED'))
                    if code != 0:
                        failures.append('%s: %s reported problems:\n      %s'
                                        % (arch, tool, o.strip().replace('\n', '\n      ')))

            # The probe: break exactly one generated region and demand the checker name it.
            # "all stamped files match" is what a checker that opened nothing would also say.
            probe = 'not run'
            sc = os.path.join(root, '_system', 'scripts', 'stamp_check.py')
            victim = None
            if got and os.path.exists(sc):
                victim = os.path.join(projected, got[0])
            elif os.path.exists(sc):
                victim = os.path.join(root, 'CLAUDE.md')
            if victim and os.path.exists(victim):
                with io.open(victim, encoding='utf-8') as fh:
                    before = fh.read()
                lines = before.split('\n')
                cut = next((i for i, ln in enumerate(lines)
                            if ln.strip() and not ln.startswith(('#', '-', '|', '<!--'))
                            and i > 4), None)
                if cut is None:
                    probe = 'no editable line found'
                else:
                    lines[cut] = lines[cut] + ' A HUMAN WROTE THIS.'
                    with io.open(victim, 'w', encoding='utf-8', newline='\n') as fh:
                        fh.write('\n'.join(lines))
                    _, o = run([sc, root])
                    caught = 'HAND-EDITED' in o
                    probe = 'hand edit caught' if caught else 'HAND EDIT MISSED'
                    if not caught:
                        failures.append('%s: a hand-edited region in %s was not reported. A '
                                        'checker that reads nothing reports all-clean too.'
                                        % (arch, os.path.basename(victim)))
                    with io.open(victim, 'w', encoding='utf-8', newline='\n') as fh:
                        fh.write(before)
            checks.append(probe)

            rows.append((arch, lang, 'NOOP %d  agents %d  workflows %d'
                         % (noop, len(got), len(got_wf)),
                         '   ' + '   '.join(checks)))

        print('')
        for arch, lang, verdict, detail in rows:
            print('  %-9s lang=%s  %s' % (arch, lang, verdict))
            print(detail)
        print('')
        for f in failures:
            print('  FAIL  %s' % f)
        if failures:
            print('')
        print('  %s' % ('VERIFICATION GREEN' if not failures else 'VERIFICATION RED'))
        print('')
        return 0 if not failures else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
