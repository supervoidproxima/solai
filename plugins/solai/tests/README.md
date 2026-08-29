# tests

Four commands, all run from `~/.claude/solai/plugins/solai`. Run the first two after any engine
change; the last two run inside `verify_engine.py` and can also be pointed at a place by hand.

```
python tests/run_tests.py                        # 178 assertions
python tests/verify_engine.py                    # four archetypes, applied twice, checked, probed
python tests/check_workflow_js.py <place>        # every projected script is real JavaScript
python tests/check_workflow_resume.py <place>    # every script replays identically
```

Each exits 0 only when green, so any of them can gate a commit.

## run_tests.py

| Module | Assertions | Covers |
|---|---:|---|
| `test_primitives.py` | 45 | `fm` 14, `stamp` 11, `regions` 13, `fsplan` 7 |
| `test_decl.py` | 49 | 20 on one class, 29 on an archetype set |
| `test_agents.py` | 34 | 22 on an agent declaration, 12 on the agent emitter |
| `test_workflows.py` | 34 | 22 on a workflow declaration, 12 on the workflow emitter |
| `test_authoring.py` | 16 | the renderers, the manifest wiring, the refusals |
| **total** | **178** | |

Every assertion carries a stable id, and the runner **refuses a run whose assertion count does
not match the declared expectation** - a deleted assertion is a silently weakened gate, so 177 of
178 passing is red for the same reason a failure is. Adding an assertion means raising `EXPECTED`
in the module that owns it. That friction is deliberate: the count is part of the gate.

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
| minimal | en | 6 | 0 | 0 |
| project | en | 42 | 5 | 3 |
| personal | **ru** | 30 | 2 | 0 |
| role | en | 34 | 4 | 2 |

Plus, per archetype that ships the checkers: 0 BLOCKER, 0 GATE, every stamped item clean, 0
broken links. `personal` runs in Russian because the label files are exercised nowhere else.

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
