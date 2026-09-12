# tests

Four commands, all run from `~/.claude/solai/plugins/solai`. Run the first two after any engine
change; the last two run inside `verify_engine.py` and can also be pointed at a place by hand.

```
python tests/run_tests.py                        # 398 assertions
python tests/verify_engine.py                    # four archetypes, applied twice, checked, probed
python tests/check_workflow_js.py <place>        # every projected script is real JavaScript
python tests/check_workflow_resume.py <place>    # every script replays identically
```

Each exits 0 only when green, so any of them can gate a commit.

## run_tests.py

| Module | Assertions | Covers |
|---|---:|---|
| `test_primitives.py` | 67 | `fm` 14, `stamp` 16, `regions` 13, `fsplan` 8, materials 6, language 6, START-HERE 4 |
| `test_decl.py` | 61 | 27 on one class, 31 on an archetype set, 3 on the card-skill emitter |
| `test_compiled.py` | 49 | 7 on loading a vault's own declarations, 7 on the fate of a hand edit, 11 on the upgrade merge, 4 on a vault with no manifest, 3 on the folder a kept class lives in, 4 on a class both sides declare, 7 on an artefact whose format holds no stamp, 6 on the six fates of a copied file |
| `test_agents.py` | 34 | 22 on an agent declaration, 12 on the agent emitter |
| `test_workflows.py` | 34 | 22 on a workflow declaration, 12 on the workflow emitter |
| `test_authoring.py` | 35 | the renderers, the manifest wiring, the refusals, `class add\|rename\|retire` |
| `test_ui.py` | 55 | 9 declarations, 6 the gate, 4 argv, 5 tier, 31 the page |
| `test_kb.py` | 25 | 7 a build end to end, 5 provenance, 6 the refusals, 4 retrieval, 3 the surface |
| `test_sensitive.py` | 11 | what `check_sensitive.py` finds, and what it refuses to print |
| `test_change.py` | 7 | claiming a change number, including sixteen threads racing for one |
| `test_release.py` | 6 | the order of a release, and each refusal naming itself |
| `test_args.py` | 14 | the shared argument reader, and every shipped script routed through it |
| **total** | **398** | |

This table was stale on 2026-09-03 - it named 178 against a suite of 241, omitted `test_ui.py`
entirely, and understated `test_primitives.py` by 17. It was stale again on 2026-09-12, at 266
against 326, missing three whole modules. The counts above were read off the harness rather
than copied forward, which is the only way a count in prose stays true - and twice now the
reading has been done only because something else brought a hand to this file.

Every assertion carries a stable id, and the runner **refuses a run whose assertion count does
not match the declared expectation** - a deleted assertion is a silently weakened gate,
so 397 of 398 passing is red for the same reason a failure is. Adding an assertion means
raising `EXPECTED`
in the module that owns it. That friction is deliberate: the count is part of the gate.

`DS-01` earned its place the same way: reintroducing the filename glob into `step_id` turned it
and `DS-02` red, and nothing else in the suite noticed.

The `evolved` case in `verify_engine.py` earned its place the same way: forcing the scaffold
back into package mode turned four of its assertions red at once - the run no longer read the
compiled declarations, the card index still named the retired class, the dictionary still
carried its schema, and the orphaned skill went unreported.

The `upgraded` case earned its place on its first run, against code the unit suite had just
passed 326/326. The merge kept the vault-only class and wrote a truthful manifest, and then
the plain run after it rewrote every generated region: the source hash named the package
manifest while the vault held the widened one. Only an end-to-end scenario could see that,
because the defect lives in the relationship between two runs.

### Mutation-tested, not assumed

19 single-edit breakages of `lib/` were each caught by the assertion claiming to cover them, and
deleting an assertion was caught by the count guard. Six assertions have been found weak this way
and fixed rather than trusted:

- `ST-02` asserted CRLF-blindness using a *trailing* CR, which `rstrip` covers on its own, so it
  passed even with line-ending normalisation removed. It now asserts a bare-CR file.
- `RG-12` never inserted into a file that already held the region, so nothing covered
  `regions.insert` delegating to `replace` - the twice-apply guarantee at its smallest.
- `EA-06` asserted an unescaped pipe between enum values; the engine escapes it, or the table row
  splits.
- `AU-14` asserted that restating an existing agent's job is refused, and it was not: the
  overlap check used Jaccard, which divides by the union, so a job that was a *subset* of a longer
  one scored 0.43 and passed. Containment fixed it.
- `WE-06`, `WE-08` and `WE-10` exist because the first workflow projection had three defects that
  two-phase declarations hid: a carry chain named for two phases, result objects interpolated into
  a prompt as `[object Object]`, and a `// ` marker prefix the shared region reader did not accept
  - so the engine could not find the markers in its own output.

## verify_engine.py

The end-to-end run that previously existed only as prose in a handoff note, which left the
engine's pass state resting on someone's word about a run nobody could repeat.

| Archetype | Language | NOOP rows | Agents | Workflows |
|---|---|---:|---:|---:|
| minimal | en | 8 | 0 | 0 |
| project | en | 49 | 5 | 3 |
| personal | **ru** | 37 | 2 | 0 |
| role | en | 41 | 5 | 2 |

Plus, per archetype that ships the checkers: 0 BLOCKER, every stamped item clean, 0 broken
links, and the one gate a freshly built place is SUPPOSED to raise - `AV-3`, nothing shipped yet.
Demanding zero gates of a place that has by construction shipped nothing is a category error, and
it is why this file had once been red on three archetypes out of four. `personal` runs in Russian
because the label files are exercised nowhere else.

**The four scenarios.** After the four archetypes, four runs mutate a vault that has already
been built and measured, so none of them moves the counts above. `evolved` retires a class and
re-applies. `upgraded` takes a package upgrade over a vault declaring a class, an agent and a
workflow the package lacks, and all three must survive it, along with the folder that
class lives in, which is deliberately a name no archetype declares, and the two keys it
changed in a class the package DOES declare. `predates` removes the compiled
manifest first and demands the same, because every scenario here builds its vault at the current
version and so every one of them had a manifest, which is why the loader's early return for a
missing one was unreachable while being the only path a real old vault takes. `answerable` writes
two cards and a document into a built vault and builds a knowledge base out of it: 4 records, the
block anchor surviving into a citation, no record out of a file the engine generated, an identical
rebuild, an output inside the vault refused, and every file in the vault hashed before and after
to prove the build wrote nothing into the thing it reads.

**The probe.** After everything reads clean, one generated region is edited and the stamp check
must name it. An all-clean report proves the checker ran, not that it works - a checker that
opened no files reports exactly the same thing. That is not hypothetical: until 0.5.0
`stamp_check` skipped `.claude/` wholesale, so it had never opened a single SKILL.md, and its
"14 stamped, all clean" was true and almost meaningless. It now reports 47 to 65 items.

## The two workflow checkers

`check_workflow_js.py` checks each projection **in two halves, the way its runner treats it**: the
`meta` region as an ES module (and then evaluated, so `phases` is confirmed to be data rather than
something that merely parses), and the `script` region inside an async function with the runtime
stubbed. Neither half is valid on the other's terms - `node --check` on the whole file trips on
the top-level `return`, and wrapping the whole file in a function trips on `export` - so a checker
that treated it as one unit would always fail, and a check that always fails is one people learn
to ignore.

`check_workflow_resume.py` is the resume gate. A runner resumes by replaying the script and
reusing every agent call whose prompt and options are unchanged, so **resume works exactly as far
as the script produces the same call sequence twice**. Each script is replayed with the runtime
stubbed and every call recorded; the two recordings must be identical; then a run is killed
mid-way and its surviving prefix must match the full run's.

**What it does not prove**, stated rather than implied: no live runner cache is exercised and no
model call is made. "The script is resumable" and "a resume was observed" are different claims.
