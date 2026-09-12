# Roadmap

What is next, what is deferred, and what has been decided against.

`kb_build.py` has said "Phase 0 of the roadmap" since it was written, and no roadmap existed.
This is it.

**What this file is not.** It is not a plan with dates. Nothing here is scheduled, because a
date invented to make a row look finished is the move the change discipline exists to catch.
A row gets a date when someone decides one, and the release that follows carries a deliverable
card that records whether the date was met.

**Status vocabulary**, closed per D6:

| Status | Means |
|---|---|
| `open` | agreed to be worth doing, not started |
| `building` | in progress |
| `done` | shipped, with the version that carried it |
| `deferred` | deliberately not now, with the reason |
| `declined` | decided against, with the reason. Reopened only by new evidence |

---

## Now

| ID | What | Why now | Status |
|---|---|---|---|
| **R-1** | Give `solai-kb` a skill surface: `SKILL.md`, a CHANGELOG row, a `Layout` line, and assertions | Three substantial scripts ship in the package and nothing routes to them. A layer with no surface is a layer that is not in the product, and the handoff of 2026-09-03 already recorded it. It is the only place in the package where D1 and D18 are both failing | `done`, row 60 |
| **R-2** | Migrate the Counselor vault | The vault it was built for cannot take a release until it is migrated, and it now keeps `platform` and `subject` through an upgrade | `open`, blocked: the post-holder has 12 uncommitted files and a bundle does not cover uncommitted work |
| **R-3** | Refresh `README.md` against the package | It said doctrine holds 18 principles and it holds 19; its `Layout` omitted two skills. Small, and it is the first file anyone reads | `done`, with this file |

## Next

| ID | What | Why | Status |
|---|---|---|---|
| **R-4** | Decide whether runs are instrumented, and to answer what | The reference architecture puts OpenTelemetry here. No question has yet been asked that the data would answer, and building an answer to no question is what `D16` publishes a ratio about. The decision comes before the build | `open`, a decision rather than a task |
| **R-5** | A vertical preset: a bundle of class declarations applied after a scaffold | University Counselor is the first. Decided already that a preset is not an archetype; `GAP-003` in the Solai vault records that no manifest can extend another, which is what makes a preset the only available shape | `open` |
| **R-6** | The harvest loop: pull a lesson from a live vault back into the package | Rows 47 to 51 of the CHANGELOG each came from one pilot and were carried across by hand. That is the package's only feedback path from a running vault, and it runs through a person's memory | `deferred` since v0.1.0, recorded in `README.md` |

## Deferred, with the reason

| ID | What | Reason |
|---|---|---|
| **R-7** | The governed tier's org layer | No vault has reached the tier. Building the enforcement for a tier nobody occupies is machinery |
| **R-8** | `counsel` as its own skill | Its assertions ship inside `check`, so the guard exists from day one. A separate skill buys a name, not a check |
| **R-9** | HTML org maps | Downstream of R-7 |
| **R-10** | Merge artefacts, fragments and runtime on `--from-package` | Those are code rather than declarations. A vault that changed one has a hand edit, and the three region fates already cover a hand edit properly. The line is between what a vault DECLARES and what it RUNS |

## Declined

| ID | What | Reason | Reopened by |
|---|---|---|---|
| **R-11** | An orchestrator, router loop and agent handoff runtime in Python | Claude Code is the runtime. Rebuilding it in `asyncio` replaces something that works with something that does not exist | Nothing short of solai running outside the harness |
| **R-12** | A vector database for the knowledge layer | The corpus fits on a laptop and full-text is enough for it. The build's four refusals matter more than recall does | A corpus that does not fit, or a recall failure someone can name |
| **R-13** | A relational store | A card is a file, a query is `grep` and a `.base` view, and a vault must outlive the tool that built it | A query nobody can express over files |
| **R-14** | Splitting into solai and solai Enterprise | One product. `CHG-005` of the Solai vault | Concurrent writing working, or someone who is not the author offering to pay |
| **R-15** | Adopting the nine classes found in the NIS ancestor into `project` | The `project` blueprint stays at five. The evidence is kept in `analysis/project/PRJ.md` as the case to reopen | The evidence in that file, argued |

---

## Done

Newest first. The CHANGELOG row is the full account; this is the index.

| Version | What | Row |
|---|---|---|
| 0.28.0 | the upgrade merge covers lookups, agents and workflows | 58 |
| 0.27.0 | an upgrade MERGES rather than replacing, for classes | 57 |
| 0.26.0 | `/solai release`, whose feature is the order | 56 |
| 0.25.0 | a change number claimed by creating the file | 55 |
| 0.24.0 | the personal-identifier guard, and a `.gitignore` whose rule is a glob over a name | 53-54 |
| 0.23.0 | `class add\|rename\|retire`, and `fsplan` learns to delete | 52 |
| 0.19.3 and earlier | the engine, the four archetypes, the persona, the setup surface, the counselor pilot's corrections | 1-51 |

## How a row gets here

A row is added when a decision is taken, not when an idea is had. The evidence for it lives in
a card in a vault, not in this file: a gap states the difference between current and desired
state, a resolution says what closes it, and a deliverable records what left and on what date.
This file is the index over those, and it carries no argument of its own.

That is also why `declined` rows name what would reopen them. A decision with no stated
reversal condition is not a decision, it is an opinion that has been written down.
