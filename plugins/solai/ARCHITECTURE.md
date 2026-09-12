# Architecture

What solai is made of, layer by layer, and where the boundary of each one runs.

`README.md` says what the package does and `doctrine.md` says why. This file says how it is
put together, and it is the file to read before changing `lib/`. It describes what exists on
2026-09-12 at version 0.31.0. Where something is absent, it is named as absent: D13 holds
here as everywhere, and an architecture diagram that draws a box nobody built is the exact
defect D1 forbids.

## The one boundary that explains the rest

**solai is not a runtime. Claude Code is the runtime.**

Every reference architecture for a multi-agent system opens with an orchestrator: an event
loop that parses intent, builds a task graph, selects agents and passes serialised context
between them. solai has no such loop and will not grow one. The loop already exists, it is
the harness the user is typing into, and its agents, tool permissions, context window and
resumption are not solai's to reimplement.

What solai contributes at that layer is **declarations the harness executes**. An agent is a
TOML file that becomes `.claude/agents/<name>.md`. A workflow is a TOML file that becomes
`.claude/workflows/<name>.js`, a script the Workflow tool runs. A card skill is a TOML file
that becomes `.claude/skills/<class>/SKILL.md`, a working `/gap` command inside the vault.

This is why the package is 10 500 lines of Python with 4 000 more in tests, rather than an
order of magnitude larger. Everything below is downstream of that one decision, and the cost
of it is real: solai inherits the harness's limits and cannot instrument what happens inside a
model call.

## The stack

Read top to bottom as a single `--apply` travels it.

| # | Layer | What it is here | Lives in | What holds it honest |
|---|---|---|---|---|
| 1 | Interview | the questions an archetype declares, asked once, stored as answers | `skills/solai/interview.md`, `_system/os/answers.toml` | `EVALS.md` E1-E3 |
| 2 | Declaration | TOML: classes, lookups, agents, workflows, the manifest | `archetypes/*/`, `common/` | `lib/decl.py`, fails fast with every reason at once |
| 3 | Generation | emitters turning one declaration into five projections | `lib/emit/`, `lib/engine.py` | `tests/run_tests.py`, 366 assertions |
| 4 | Plan and write | four write modes, region merge, rollback manifest | `lib/fsplan.py`, `lib/regions.py`, `lib/stamp.py` | `--plan` default; applying twice is provably a no-op |
| 5 | Storage | the vault: Markdown plus YAML, and its compiled declarations | the vault, `_system/os/` | `runtime/validate_cards.py`, `check_links.py` |
| 6 | Knowledge | a built `kb/`: one record per citable unit, SQLite FTS, a manifest | `skills/solai-kb/` | four build refusals; `tests/test_kb.py`, 25 assertions; the `answerable` scenario |
| 7 | Safety | refusals, the human gate, the personal-data guard | `skills/solai/refusals.md`, `runtime/check_sensitive.py` | `tests/test_sensitive.py`, D19 |
| 8 | Verification | three gates, run last, immediately before a push | `tests/`, `skills/solai-release/` | `release.py` refuses a dirty tree outright |
| 9 | Observability | a build ledger and a dashboard. No traces, no metrics | `_system/os/build.md`, `runtime/gen_dashboard.py` | **thin, see below** |

## 1-2. Declarations

One file, one class, one place a fact is stated. Five projections come out of it and none is
authoritative: the data dictionary, the `card-index` region of `CLAUDE.md`, the card skill,
the Obsidian base view, and the runtime validator, which reads the TOML as data rather than
having code generated from it.

TOML for three reasons, in order of weight: `tomllib` is stdlib and pyyaml is not installed
on the target machine; comments are allowed, and a declaration carries the rationale for its
own fields; and `tomllib` is read-only, which makes it structurally impossible for the engine
to quietly rewrite a declaration it was only supposed to read.

**Three loaders, and which one runs is printed on every run.**

| Loader | Reads | When |
|---|---|---|
| `load_archetype` | the package | a first build |
| `load_compiled` | `_system/os/` | every later run. Classes are discovered by LISTING the directory, so deleting a file IS the retirement |
| `load_merged` | both | `--from-package`, an upgrade. Package-only taken, vault-only kept, both to the package |

`load_compiled` is the reason a vault can rename a class and still regenerate truthfully.
`load_merged` is the reason an upgrade does not delete what only the vault declared. Those
two directions are the whole contract between a vault and the package that built it, and
`tests/verify_engine.py` runs one scenario for each: `evolved` and `upgraded`.

## 3-4. Generation, plan and write

Emitters know nothing about the filesystem; the engine is the only thing that writes. A plan
is built in full, printed as a table, and only then applied. Every row carries a mode:

| Mode | Belongs to | On a re-run |
|---|---|---|
| `generated` | the engine | rewritten |
| `seeded` | you, after the first write | never touched again |
| `merged` | you, except marker-delimited regions | per region, so one edited paragraph costs one region |
| `copied` | the package, tracked by hash | replaced when the source moves |

A generated region carries `source-sha` and `body-sha`. The check distinguishes STALE, where a
source moved, from HAND-EDITED, where the body no longer matches its stamp, and a hand edit
is never overwritten. It has three fates rather than one: RECONCILED where the declaration has
caught up with the edit, ADOPTED where `--adopt <region> --because CHG-NNN` has signed for it,
and HAND-EDITED otherwise.

**The source hash is over what the plan writes, not over what sits at `arch.root`.** That
distinction looks pedantic and was a real defect: under a merge the two differ, and hashing
the wrong one made every region in the vault read STALE on the next ordinary run.

## 5. Storage

Plain Markdown with YAML frontmatter, in a folder the user already opens in Obsidian. No
database, and the absence is the design: state lives in a field a generator reads (D2), and a
field in a text file is greppable, diffable, versionable and readable without this package
installed. A vault outlives the tool that built it.

`_system/os/` holds the compiled declarations, the answers, the apply manifest and the build
ledger. It is explicitly out of scope of the vault's own governance, because a vault auditing
its own engine state is a category error.

## 6. Knowledge

`skills/solai-kb/` builds a `kb/` out of a vault: one record per citable unit, a SQLite
full-text index, and a manifest saying what went in and what was refused and why. Provenance
is a corpus hash over the selected file set rather than a commit, because the vaults it reads
are deliberately not in git. `kb_ask.py` retrieves and formats; it does not write the answer.
`kb_site.py` renders one self-contained HTML registry.

No vector store and no embeddings. The reference architecture reaches for Chroma or Qdrant
here; this is full-text over a corpus that fits on a laptop, and the build refuses on four
conditions that matter more than recall does: a cloud placeholder that is not really on disk,
a citation anchor that is not in the text it came from, a non-deterministic rebuild of an
unchanged corpus, and a record count that fell further than the allowed margin.

`SKILL.md` is the surface, with `build`, `ask` and `site` as its verbs, `kb.example.toml`
as the exemplar its rules file is copied from, and `--dry-run` before a real build by the same
rule that puts `--plan` before `--apply` everywhere else. `tests/test_kb.py` builds a vault in
a temporary folder and asserts what is selected, what is refused by name, what lands on disk,
and that the same corpus rebuilds to the same bytes.

The pairing with the rest of the stack is asserted where it can be: the `answerable` scenario in
`verify_engine.py` builds a knowledge base out of a vault THIS ENGINE scaffolded, and hashes
every file in that vault before and after. "It does not write into the vault" is this layer's
whole boundary, and a claim of that shape cannot be read off the code.

Two gates are asserted structurally rather than exercised, and the test module says so on its
face: the cloud placeholder check, because no test can make a file Windows reports as living
somewhere else, and nothing at all about whether the selection rules select the right
documents, which is a human reading of the refusal list in the manifest.

## 7. Safety

Four mechanisms, and only the first is advisory:

- **Refusals.** The engine names what it will not do and why, and the persona is forbidden by
  `E5` from relaying a refusal as anything other than what it said.
- **The human gate.** `--plan` is the default everywhere. Nothing writes without a second
  command from a person who has seen the table.
- **`check_sensitive.py`.** Walks the whole tree rather than a declared list and sorts what it
  finds by what git would do with it. EXPOSED, untracked and unignored, is the only state that
  turns the exit code red. It never prints an identifier it found, and it counts binaries as
  unscanned rather than passing over them in silence.
- **D19.** Nothing is deleted by a script. `fsplan.Plan.delete` exists only so that a class
  retirement leaves a row in a table and something to roll back to.

## 8. Verification

| Gate | Proves |
|---|---|
| `tests/run_tests.py` | 366 assertions over the primitives, loaders and emitters |
| `tests/verify_engine.py` | four archetypes built, applied twice, checked and probed, plus `evolved` and `upgraded` |
| `tests/verify_install.py` | the installer's branches on a machine that has nothing |

Two properties of this layer are load-bearing. **The count is part of the gate**: the runner
refuses a run whose assertion count does not match the declared expectation, so a deleted
assertion is caught rather than silently weakening the suite. And **the gates run last**, in
`release.py`, immediately before the push rather than before the commit that precedes it. That
ordering exists because a release once ran three green gates, then bumped a version, then
committed the result, and the bump had truncated `lib/__init__.py`.

## 9. Observability

The thin layer, stated as thin. What exists: `_system/os/build.md`, an append-only ledger of
what each apply did; `apply-manifest.json`, which `--rollback` reads; and a generated
dashboard reflecting the vault after an apply.

What does not exist: traces, spans, latency, token accounting, and any export to a collector.
The reference architecture puts OpenTelemetry here. Two honest reasons it is absent. The
first is that the calls worth tracing happen inside Claude Code, and instrumenting them from a
plugin would measure the wrapper rather than the work. The second is that no question has yet
been asked that this data would answer, and building an answer to no question is precisely the
ratio `D16` publishes. It is `R-4`, a candidate rather than a decision.

## What is deliberately not here

| Not built | Why |
|---|---|
| an orchestrator, a router loop, agent handoff code | the harness is the runtime |
| Pydantic or any runtime schema library | declarations are validated at load by `lib/decl.py`, which reports every error at once, and adding a dependency costs more on the target machine than it returns |
| a relational store | a card is a file; a query is `grep` and a `.base` view |
| a vector database | see layer 6 |
| the governed tier's org layer | recorded as deferred in `README.md` since v0.1.0 |
| `counsel` as its own skill | its assertions ship inside `check`, so the guard exists from day one |

Each of these is a decision, and each is reversible by evidence. None of them is an oversight,
which is why they are in a table rather than in a backlog.

## Where this file is wrong the moment it is written

An architecture document is a projection of a system, and this package's own doctrine says a
projection that is not generated will drift. This one is hand-written and therefore will.
Three things already drifted before it existed: `README.md` said doctrine holds 18 principles
against 19; its `Layout` block omitted `skills/solai-kb/` and `skills/solai-release/`; and
`tests/README.md` has now been found stale three times, at 178 against 241, at 266 against 330,
and in six places at 0.28.0. This file then drifted the same way within a day of predicting it:
two rows here said 330 while the suite stood at 355, because the release that moved the number
edited the test README and not this one.

The rule for this file is therefore the same one the test README carries: **counts are read
off the thing, never copied forward**, and the version at the top is updated in the same commit
as the change it describes or not at all.
