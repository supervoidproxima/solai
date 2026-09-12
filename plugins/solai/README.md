# solai

Set up, audit and adopt Obsidian vaults from one command.

Built out of two working vaults that each held half of a good answer. `Fangorn` grew a
governance layer: a constitution, an org chart, declaration schemas that mark unenforceable
fields in the open, a hash-stamped dependency index, an append-only judgement log. A
consulting project vault grew the domain machinery: card registries, closed vocabularies, a
data dictionary, a verification constitution, scripts with a run-order contract. Neither could
reproduce itself, and starting a third vault meant retyping one half and forgetting the other.

## Install

```
/plugin marketplace add supervoidproxima/solai
/plugin install solai@solai
```

Then `/solai`.

## The one idea

**Declarations are TOML. Projections are Markdown. Nothing is both.**

A card class is declared once, in one file. Five things are generated from it and none of them
is authoritative:

```
archetypes/project/classes/gap.toml
  -> _system/data-dictionary.md   status matrix, enums, schema table, link rules
  -> CLAUDE.md                    card-index region: routing only, never a field name
  -> .claude/skills/gap/SKILL.md   a working /gap command, in the vault
  -> registry.base                 one Obsidian view
  -> validate_cards.py             reads the TOML at runtime; assertions are data, not codegen
```

One 130-line declaration replaces roughly 900 lines of hand-maintained Markdown across five
files, and makes their divergence impossible rather than a discipline problem. The vault this
package generates has a 185-line CLAUDE.md where the source vault has 102 KB, most of it
schema prose duplicated from its own data dictionary.

## Verbs

| Verb | Writes | What it does |
|---|---|---|
| *(bare)* | nothing | tier, assertion counts, the ratio, waivers, deferrals |
| `new` | scaffolds | counts first, interviews, plans, then applies |
| `adopt <path>` | a report | read-only conformance probe over an existing vault |
| `check [--fix]` | `--fix` only | the vault's own validator, stamp check and link check |
| `class <name>` | scaffolds | declare a class, regenerate its five projections |
| `change "<what>"` | a record | mint the next change record |
| `route "<intent>"` | nothing | resolve who owns a piece of work, or refuse and name the candidates |

## Re-running is safe

Four write modes and one classifier. `generated` files belong to the engine; `seeded` files
are written once and then belong to you; `merged` files are yours with marker-delimited
regions belonging to the engine; `copied` files are byte copies tracked for upgrade.

A hand edit is never overwritten. Because merge is per region, editing one paragraph of
`CLAUDE.md` costs that one region, not the file. `--plan` is the default everywhere,
`--rollback` restores from a manifest, and applying twice in a row is provably a no-op.

## What it refuses

A greenfield folder with nothing in it cannot be initialised above `light`: four files, and a
stated reason. Higher tiers need content, or a named first artefact with a date, which is then
stored as the denominator of every ratio the package reports.

This package declares `induces: authoring-instead-of-shipping`. Its own generated files count
on the document side of the ratio they report, and may not be argued out of that column. That
is not decoration: the vault this pattern came from computed its own verdict at 49 documents to
4 artefacts, and a tool that builds tools is the most dangerous possible instance of it.

## Layout

```
doctrine.md          19 principles, ranked. Ships here, never copied into a vault
ARCHITECTURE.md      the stack in nine layers, and where each boundary runs
ROADMAP.md           what is next, what is deferred, what has been decided against
conventions.md       kebab-case naming, frontmatter, handoff at half context, the dashboard
skills/solai/        the persona you talk to
skills/solai-scaffold/  the engine
skills/solai-adopt/  the read-only probe
skills/solai-release/   the release order: gates last, immediately before the push
skills/solai-kb/     a knowledge base built out of a vault: build, ask, render a registry
lib/                 primitives (fm, stamp, regions, fsplan), declarations, emitters
archetypes/          minimal, project, personal, role
runtime/             copied into each vault: validator, stamp check, link check, dashboard
shared/              protocols the generated card skills read
common/labels/       output-language strings, so the language question is structural
```

## Not built yet, on purpose

The governed tier's org layer; `counsel` as its own skill (its assertions ship inside `check`,
so the guard exists from day one); HTML org maps. Each is recorded as deferred rather than left
implied, because an undeclared deferral is the same defect as an undeclared write.

The harvest loop, which pulls a lesson from a live vault back into the package, stopped being one
of them on 2026-09-13. It was deferred for four releases and cost a fix that lived correct in a
vault for days while the package shipped the defect to everyone, that vault included. `R-6` now
names what it is: a verb that reads every copied file a vault has changed and prints the diff.

The `personal` and `role` archetypes were deferred at v0.1.0 and built at v0.2.0. Neither
needed a line of `lib/` changed, which was the test they were there to run.
