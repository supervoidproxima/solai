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

The three card archetypes moved by one more when `mint_change.py` joined the copied
runtime. `minimal` does not take it: it has a change folder but no `_system/scripts`, so the
number it mints is minted by hand and that is a real gap rather than a decision.

All four moved by one again when a seeded `.gitignore` became an artefact, `minimal`
included: a vault with no card classes can still be put under git beside a sync client, and
the rule that failed in CHG-134 does not care what an archetype declares.

The three card archetypes moved by one each when `check_sensitive.py` joined the copied
runtime. It ships to every archetype that carries scripts rather than only to one that says
it holds data about people, because the failure it guards against is a file nobody declared:
the vault that met it had 728 children's identifiers in a sync client's conflict copy, and
nothing in a declaration would have mentioned that file. `minimal` still takes none of the
runtime.

Every archetype then gained one more row: `_system/os/manifest.toml`, the last piece of the
declaration to be compiled into the vault. With it a place can be regenerated from its own
declarations rather than only validated against them.

The three card archetypes gained one more: `_system/scripts/readme.md`, the run-order
contract `CLAUDE.md` had promised since the first release and the package had never
shipped. `minimal` does not take it, for the same reason it takes no `state.md`.

Two extra checkers run against any place that carries workflows: `check_workflow_js.py` proves
each projection is real JavaScript with an evaluable `meta` literal, and
`check_workflow_resume.py` replays each script twice with the runtime stubbed and demands an
identical call sequence, then kills a run mid-way and demands the surviving prefix match. That
is the property a resume actually depends on. A live runner cache and a real model call remain
unexercised, and are stated as such rather than implied.

Four scenarios run after the four archetypes and none touches the counts above, because
each mutates a vault that has already been built and measured. `evolved` retires a class from
a `role` vault and re-applies. `upgraded` is its mirror: a `project` vault declares a class, an
agent and a workflow that the package does not carry, and edits a class the package DOES
carry in the two keys a vault owns, and then takes a package upgrade, which must keep all
four. Those two directions are the whole contract between a vault and the
package it was built from.

`predates` is the third. `upgraded` passes only because the vault it builds always carries a
compiled manifest, and the one vault old enough to need an upgrade does not: the manifest is
removed and the same upgrade must still keep the class, the agent and the workflow that only
the vault declares. A guard that switches itself off on old vaults guards nothing, and no
scenario could see it while every scenario built its vault at the current version.

`answerable` is the fourth: cards are written into a built vault and a knowledge base is built
out of it. The unit suite proves the build's refusals against a corpus it invents; this proves
the pairing - that a vault THIS ENGINE produced is a corpus the build can read, that no file
the engine generated becomes an answer, and that the vault is not written to. The last one is
asserted by hashing every file in the vault before and after and demanding not one byte moved,
because "it does not write into the vault" is the layer's whole boundary and a claim of that
shape cannot be read off the code.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SCAFFOLD = os.path.join(PKG, 'skills', 'solai-scaffold', 'scaffold.py')

# The class the `upgraded` scenario declares in a vault and nowhere else. Deliberately
# minimal and link-free: it is standing in for `deliverable` in the vault that invented it,
# and what is being tested is whether an upgrade keeps it, not what it says.
#
# It lives at `zetas`, which NO archetype declares. It used to live at `registry/zeta`, under a
# folder `project` declares for its own reasons, and so did the one real vault's own class, and
# both therefore passed a merge that kept the class and dropped the folder it needed. A fixture
# that shares an accidental property with the only live example confirms whatever that property
# permits: GAP-008.
ZETA = '''\
schema = 1
class     = "zeta"
prefix    = "ZET"
folder    = "zetas"
skill     = "zeta"
title     = "Zeta"
purpose   = "Declared by one vault and by no archetype."

[status]
lifecycle = ["open"]
terminal  = ["closed"]
default   = "open"

[[fields]]
name     = "title"
type     = "scalar"
card     = "1"
required = true
'''

# archetype, output language, expected NOOP plan rows, agents projected, workflows projected.
# Each agent and each workflow contributes two rows: the projection under `.claude/` and its
# declaration compiled into `_system/os/`.
# Gates a correctly built, empty place is SUPPOSED to raise. A gate is not an invalidity:
# `validate_cards.py` exits non-zero on BLOCKER alone, and AV-2 says of itself that it "is
# reported every run until it is not true". Demanding zero gates from a place that has by
# construction shipped nothing is a category error, and it is why this file had been red:
# three of the four archetypes failed on the one gate they are built to raise.
FRESH_GATES = {'AV-3'}

# The NOOP count rose by one per archetype in 0.32.0, for `_system/os/stamps.json`, the record
# for the artefacts whose own format carries no stamp, by one again in 0.33.0 for
# `_system/scripts/_args.py`, the one argument reader the nine scripts share, and by one again in
# 0.35.0 for `_system/scripts/_wikilink.py`, the one wikilink pattern they share. All three are
# ordinary planned files, so a second run reports each NOOP like any other.
CASES = (
    ('minimal', 'en', 11, 0, 0),
    ('project', 'en', 52, 5, 3),
    ('personal', 'ru', 40, 2, 0),
    ('role', 'en', 44, 5, 2),
)

ANSWERS = ('remit=A throwaway place built only to verify the engine.',
           'first_artefact=One verification report that leaves this place.')

KB_BUILD = os.path.join(PKG, 'skills', 'solai-kb', 'kb_build.py')
KB_ASK = os.path.join(PKG, 'skills', 'solai-kb', 'kb_ask.py')

# The rules file the `answerable` scenario writes beside its output. It names only the card
# folders and `sources/`: everything the engine generated is left outside the selection, which
# is the arrangement a real vault uses and the one the scenario then checks was honoured.
KB_RULES = '''\
name  = "verify"
vault = "%s"

[include]
paths = ["registry/**/*.md", "sources/*.md"]

[granularity]
card = ["gap", "question"]
'''

# Two cards and one document, written into a built vault the way a user writes them. The
# document carries two heading levels and a block anchor, so the clause path and the anchored
# citation are exercised against real engine-built surroundings rather than a fixture.
CORPUS = (
    ('registry/gaps/GAP-001.md',
     '---\nid: GAP-001\ntype: gap\ndate: 2026-09-12\nstatus: on-review\n'
     'text: "Reconciliation is done by hand"\n---\n\n'
     'The reconciliation between the two ledgers is done by hand every month.\n'),
    ('registry/questions/QST-001.md',
     '---\nid: QST-001\ntype: question\ndate: 2026-09-12\nstatus: open\n'
     'question: "Who owns the reconciliation"\n---\n\n'
     'Nobody has named an owner for the monthly reconciliation.\n'),
    ('sources/2026-09-12-handbook.md',
     '---\nid: HBK-001\ntype: note\ntitle: Handbook\n---\n\n'
     '## Part one\n\n### 1.1 Monthly close ^b4c5d6\n\n'
     'The close runs on the fifth working day.\n\n'
     '### 1.2 Exceptions\n\nAn exception is signed by the owner.\n'),
)


def run(args, cwd=None):
    p = subprocess.run([sys.executable] + [str(a) for a in args], cwd=cwd,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def num(pattern, text, default=None):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


def snapshot(root):
    """Every file under `root`, by relative path and digest.

    A read-only claim about a tool is only as good as what was compared afterwards. A file
    count would miss an edit in place and a timestamp would miss nothing but would also fire
    on a clock, so this hashes the bytes.
    """
    out = {}
    for base, _dirs, names in os.walk(root):
        for name in names:
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace('\\', '/')
            with io.open(path, 'rb') as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


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

        # ------------------------------------------------------- the vault evolves
        # The executable form of the defect this release exists to fix. A `role` place is
        # built, then mutated the way a real one was - a class retired by deleting its
        # declaration, and the link that pointed at it removed - and re-applied. The claim
        # is that the projections follow the vault's OWN declarations: before this, they
        # followed the package, so a place could be validated correctly and regenerated
        # wrongly, and its CLAUDE.md went on naming a class that no longer existed.
        root = os.path.join(tmp, 'role')
        checks, ok = [], True
        if os.path.isdir(root):
            os.remove(os.path.join(root, '_system', 'os', 'classes', 'deliverable.toml'))
            duty = os.path.join(root, '_system', 'os', 'classes', 'duty.toml')
            text = io.open(duty, encoding='utf-8').read()
            i = text.index('[[links]]')
            kept = [b for b in text[i:].split('[[links]]')
                    if b.strip() and 'target     = "deliverable"' not in b]
            text = text[:i] + ''.join('[[links]]' + b for b in kept)
            text = text.replace('"deliverable", ', '').replace(', "deliverable"', '')
            io.open(duty, 'w', encoding='utf-8', newline='\n').write(text)

            code, out = run([SCAFFOLD, root, '--apply'])
            claude = io.open(os.path.join(root, 'CLAUDE.md'), encoding='utf-8').read()
            index_region = claude.split('solai:begin card-index')[-1].split('solai:end')[0]
            dd = io.open(os.path.join(root, '_system', 'data-dictionary.md'),
                         encoding='utf-8').read()

            if 'declarations: this vault' not in out:
                failures.append('evolved: the run did not read the compiled declarations')
                ok = False
            if 'DLV' in index_region or 'Deliverable' in index_region:
                failures.append('evolved: the card index still names the retired class')
                ok = False
            if 'DLV-NNN' in dd:
                failures.append('evolved: the data dictionary still carries the retired schema')
                ok = False
            if not os.path.exists(os.path.join(root, '.claude', 'skills', 'deliverable',
                                               'SKILL.md')):
                failures.append('evolved: the orphaned skill was DELETED. D7 requires a '
                                'retirement to name the fate of its artefacts, not assume one')
                ok = False
            if 'projects a class no longer declared' not in out:
                failures.append('evolved: the orphaned skill was not reported as a deferral')
                ok = False
            code2, out2 = run([SCAFFOLD, root, '--apply'])
            if 'nothing to do' not in out2:
                failures.append('evolved: the run after the change is not a NOOP')
                ok = False
            checks.append('retired a class, regenerated from the vault: %s'
                          % ('ok' if ok else 'FAILED'))
            rows.append(('evolved', 'en', 'role, one class retired', '   ' + checks[0]))

        # ------------------------------------------------------- the vault upgrades
        # The other half of the same rule. `--from-package` re-imports the archetype, and
        # used to re-import it WHOLE: a class the vault declared and the package did not was
        # deleted along with its folder, its skill and its row in every generated index. A
        # vault declares one class of its own here, the way a vault does - by putting the
        # declaration in `_system/os/classes/` - and then takes a package upgrade.
        root = os.path.join(tmp, 'project')
        checks, ok = [], True
        if os.path.isdir(root):
            io.open(os.path.join(root, '_system', 'os', 'classes', 'zeta.toml'), 'w',
                    encoding='utf-8', newline='\n').write(ZETA)
            # A class the package ALSO declares, edited in the two keys a vault owns.
            # The rule used to be that the package won whole, and that cost one live
            # vault a `filename = "slug"` it had decided on and recorded: nineteen
            # cards were invalid the second the upgrade landed. GAP-009, RES-009.
            shared = io.open(os.path.join(PKG, 'archetypes', 'project', 'classes',
                                          'gap.toml'), encoding='utf-8').read()
            shared = shared.replace('schema = 1', 'schema = 1\n\nfilename = "slug"', 1)
            shared = shared.replace('columns = ["file.name",',
                                    'columns = ["file.name", "id",', 1)
            io.open(os.path.join(root, '_system', 'os', 'classes', 'gap.toml'), 'w',
                    encoding='utf-8', newline='\n').write(shared)
            # An agent and a workflow of the vault's own, renamed from what the package
            # ships. A vault declares one the same way it declares a class - by putting the
            # file in `_system/os/` - so an upgrade has the same duty towards all three.
            for kind, src, old, new in (
                    ('agents', 'scout.toml', 'agent = "scout"', 'agent = "probe"'),
                    ('workflows', 'review.toml', 'workflow = "review"',
                     'workflow = "probe-job"')):
                text = io.open(os.path.join(PKG, 'common', kind, src),
                               encoding='utf-8').read()
                assert old in text, 'the %s fixture edit found nothing' % kind
                name = new.split('"')[1]
                io.open(os.path.join(root, '_system', 'os', kind, '%s.toml' % name), 'w',
                        encoding='utf-8', newline='\n').write(text.replace(old, new, 1))
            run([SCAFFOLD, root, '--apply'])

            code, out = run([SCAFFOLD, root, '--apply', '--from-package'])
            claude = io.open(os.path.join(root, 'CLAUDE.md'), encoding='utf-8').read()
            index_region = claude.split('solai:begin card-index')[-1].split('solai:end')[0]
            manifest = io.open(os.path.join(root, '_system', 'os', 'manifest.toml'),
                               encoding='utf-8').read()

            if 'kept: zeta' not in out:
                failures.append('upgraded: the run did not report the kept class')
                ok = False
            if not os.path.exists(os.path.join(root, '_system', 'os', 'classes', 'zeta.toml')):
                failures.append('upgraded: the vault-only DECLARATION was deleted by an '
                                'upgrade. This is the whole defect')
                ok = False
            if 'ZET' not in index_region:
                failures.append('upgraded: the card index dropped the vault-only class')
                ok = False
            if not os.path.exists(os.path.join(root, '.claude', 'skills', 'zeta', 'SKILL.md')):
                failures.append('upgraded: the vault-only class lost its skill')
                ok = False
            if '"zeta"' not in manifest or '"probe"' not in manifest \
                    or '"probe-job"' not in manifest:
                failures.append('upgraded: the compiled manifest does not list everything the '
                                'upgrade kept, so the next plain run reads it as drift')
                ok = False
            # The folder the kept class lives in, which no archetype declares. Keeping a
            # declaration and not the place it lives kept the class and then refused the
            # set the merge had just built.
            if 'path = "zetas"' not in manifest:
                failures.append('upgraded: the merged manifest does not declare the folder '
                                'the kept class lives in, so the next run refuses the vault')
                ok = False
            if not os.path.isdir(os.path.join(root, 'zetas')):
                failures.append('upgraded: the folder of the kept class was never created, '
                                'so the vault declares a folder that is not there')
                ok = False
            shared_now = io.open(os.path.join(root, '_system', 'os', 'classes',
                                              'gap.toml'), encoding='utf-8').read()
            if 'filename = "slug"' not in shared_now:
                failures.append('upgraded: the upgrade un-decided what this vault decided '
                                'about a class the package also declares. It differed only '
                                'in what the vault owns, and the package took it anyway')
                ok = False
            if 'kept' not in out or "'gap'" not in out:
                failures.append('upgraded: keeping the vault half of a shared class was not '
                                'reported, so a reader cannot tell it happened')
                ok = False
            for kept in (('_system', 'os', 'agents', 'probe.toml'),
                         ('_system', 'os', 'workflows', 'probe-job.toml'),
                         ('.claude', 'agents', 'probe.md'),
                         ('.claude', 'workflows', 'probe-job.js')):
                if not os.path.exists(os.path.join(root, *kept)):
                    failures.append('upgraded: the upgrade dropped %s. An agent and a workflow '
                                    'are declared the way a class is' % '/'.join(kept))
                    ok = False
            code2, out2 = run([SCAFFOLD, root, '--apply', '--from-package'])
            if 'nothing to do' not in out2:
                failures.append('upgraded: the upgrade is not idempotent')
                ok = False
            code3, out3 = run([SCAFFOLD, root, '--apply'])
            if 'nothing to do' not in out3:
                failures.append('upgraded: a plain run after the upgrade is not a NOOP, so the '
                                'merged manifest and the compiled declarations disagree')
                ok = False
            checks.append('kept what only the vault declared, through an upgrade: %s'
                          % ('ok' if ok else 'FAILED'))
            rows.append(('upgraded', 'en', 'project, a class, an agent and a workflow the package lacks',
                         '   ' + checks[0]))

        # ------------------------------------------------------- the vault predates the manifest
        # The same upgrade, against a vault with no compiled manifest at all. Every scenario
        # above builds its vault at the current version, so every one of them has a manifest,
        # and the loader's early return for a missing one was therefore unreachable from here
        # while being the only path a real old vault takes. It deleted two classes from the
        # counselor. GAP-007 and RES-007 of the Solai vault.
        root = os.path.join(tmp, 'project')
        checks, ok = [], True
        manifest = os.path.join(root, '_system', 'os', 'manifest.toml')
        if os.path.isdir(root) and os.path.exists(manifest):
            os.remove(manifest)
            code, out = run([SCAFFOLD, root, '--apply', '--from-package'])
            claude = io.open(os.path.join(root, 'CLAUDE.md'), encoding='utf-8').read()
            index_region = claude.split('solai:begin card-index')[-1].split('solai:end')[0]

            if 'kept: zeta' not in out:
                failures.append('predates: an upgrade with no manifest reported nothing kept. '
                                'A missing manifest says the vault is OLD, never that it '
                                'declares nothing')
                ok = False
            if 'ZET' not in index_region:
                failures.append('predates: the card index dropped the vault-only class')
                ok = False
            for kept in (('_system', 'os', 'classes', 'zeta.toml'),
                         ('_system', 'os', 'agents', 'probe.toml'),
                         ('_system', 'os', 'workflows', 'probe-job.toml'),
                         ('.claude', 'skills', 'zeta', 'SKILL.md'),
                         ('.claude', 'agents', 'probe.md'),
                         ('.claude', 'workflows', 'probe-job.js')):
                if not os.path.exists(os.path.join(root, *kept)):
                    failures.append('predates: the upgrade dropped %s from a vault whose only '
                                    'fault was being old' % '/'.join(kept))
                    ok = False
            if not os.path.exists(manifest):
                failures.append('predates: the manifest was not written back, so the next run '
                                'takes this path again and nothing is ever recorded')
                ok = False
            code2, out2 = run([SCAFFOLD, root, '--apply'])
            if 'nothing to do' not in out2:
                failures.append('predates: a plain run after the upgrade is not a NOOP, so the '
                                'synthesised manifest disagrees with what is beside it')
                ok = False
            checks.append('upgraded a vault with no compiled manifest: %s'
                          % ('ok' if ok else 'FAILED'))
            rows.append(('predates', 'en', 'project, manifest removed before the upgrade',
                         '   ' + checks[0]))

        # ------------------------------------------------------- the vault is answerable
        # The knowledge layer's end of the contract. A vault the engine built is turned into a
        # kb/ that lives outside it. The unit suite proves the refusals against a corpus it
        # invents; what can only be proved here is the pairing with a real built vault.
        root = os.path.join(tmp, 'project')
        kb_home = os.path.join(tmp, 'kb-project')
        checks, ok = [], True
        if os.path.isdir(root):
            os.makedirs(kb_home)
            for rel, text in CORPUS:
                path = os.path.join(root, *rel.split('/'))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                io.open(path, 'w', encoding='utf-8', newline='\n').write(text)
            io.open(os.path.join(kb_home, 'kb.toml'), 'w', encoding='utf-8',
                    newline='\n').write(KB_RULES % root.replace('\\', '/'))
            out_dir = os.path.join(kb_home, 'kb')

            before = snapshot(root)
            code, out = run([KB_BUILD, kb_home, '--dry-run'])
            if code != 0 or os.path.isdir(out_dir):
                failures.append('answerable: the dry run exited %d%s'
                                % (code, ' and wrote a kb anyway' if os.path.isdir(out_dir)
                                   else ''))
                ok = False

            code, out = run([KB_BUILD, kb_home])
            if code != 0:
                failures.append('answerable: the build exited %d over a vault this engine '
                                'built:\n      %s' % (code, out.strip()[-600:].replace(
                                    '\n', '\n      ')))
                ok = False
            missing = [n for n in ('records.jsonl', 'index.sqlite', 'manifest.json', 'docs')
                       if not os.path.exists(os.path.join(out_dir, n))]
            if missing:
                failures.append('answerable: the build wrote no %s' % ', '.join(missing))
                ok = False

            man, recs = {}, []
            if not missing:
                man = json.loads(io.open(os.path.join(out_dir, 'manifest.json'),
                                         encoding='utf-8').read())
                recs = [json.loads(ln) for ln in
                        io.open(os.path.join(out_dir, 'records.jsonl'),
                                encoding='utf-8').read().splitlines() if ln.strip()]

            # Two cards and a two-clause document. Exact, because the corpus is this file's
            # own: a count that moves here means the extraction changed, which is the one
            # thing a citation cannot survive quietly.
            if len(recs) != 4:
                failures.append('answerable: %d records from a corpus of 2 cards and a '
                                '2-clause document, expected 4' % len(recs))
                ok = False
            kinds = sorted({r['kind'] for r in recs})
            if kinds != ['card.gap', 'card.question', 'document.section']:
                failures.append('answerable: record kinds %s, expected a card per card class '
                                'and the document split into sections' % kinds)
                ok = False
            if not [r for r in recs if r.get('anchor') == 'b4c5d6'
                    and r['cite_kind'] == 'anchor']:
                failures.append('answerable: the block anchor in the document did not survive '
                                'into a citation, so the deep link is approximate')
                ok = False

            # Nothing the engine generated may become an answer. The selection is stated in
            # kb.toml, and this is the check that it was honoured rather than merely written.
            leaked = sorted({r['path'] for r in recs
                             if r['path'].startswith(('.claude/', '_system/'))})
            if leaked:
                failures.append('answerable: %d records came out of generated engine files: %s'
                                % (len(leaked), ', '.join(leaked[:3])))
                ok = False

            after = snapshot(root)
            if after != before:
                changed = sorted(set(after) ^ set(before)) or \
                    sorted(k for k in after if before.get(k) != after[k])
                failures.append('answerable: the build changed %d file(s) in the vault it '
                                'reads: %s' % (len(changed), ', '.join(changed[:3])))
                ok = False

            code, out2 = run([KB_BUILD, kb_home])
            man2 = json.loads(io.open(os.path.join(out_dir, 'manifest.json'),
                                      encoding='utf-8').read()) if not missing else {}
            if code != 0 or man2.get('records_hash') != man.get('records_hash'):
                failures.append('answerable: the same corpus and builder rebuilt to different '
                                'records (%s then %s)'
                                % (man.get('records_hash'), man2.get('records_hash')))
                ok = False

            code, out3 = run([KB_ASK, kb_home, 'reconciliation by hand'])
            if code != 0 or 'GAP-001' not in out3:
                failures.append('answerable: retrieval did not find the card that carries the '
                                'question words')
                ok = False

            code, out4 = run([KB_BUILD, kb_home, '--out', os.path.join(root, 'kb')])
            if code == 0 or 'refusing to build inside the vault' not in out4:
                failures.append('answerable: a build whose output lands inside the vault was '
                                'not refused by name')
                ok = False

            checks.append('built a kb out of a built vault, wrote nothing into it: %s'
                          % ('ok' if ok else 'FAILED'))
            rows.append(('answerable', 'en',
                         'project, %d records, %d files refused'
                         % (len(recs), len(man.get('refused', []))),
                         '   ' + checks[0]))

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
