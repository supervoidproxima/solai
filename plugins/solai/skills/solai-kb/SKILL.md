---
name: solai-kb
description: Build a knowledge base out of a vault, ask it questions that come back with citations, and render it as one self-contained HTML registry. Reads a vault and never writes into one. Refuses to publish a doubtful build rather than shipping it quietly.
scope: global
trigger_phrases:
  - "/solai kb"
  - "build a knowledge base"
  - "ask the knowledge base"
  - "generate the clause registry"
permissions:
  read: true
  write: true
  execute: true
  network: false
---

=== SOLAI - KNOWLEDGE BASE ===

ARGUMENTS: $ARGUMENTS
One verb: `build <kb>` · `ask <kb> "<question>"` · `site <kb>`. An unknown verb prints this
list and stops. `build` without `--dry-run` first is refused by this skill, not by the script.

## THREE THINGS, THREE HOMES

The build keeps them apart, and every refusal below follows from the separation.

| Thing | Holds | Receives |
|---|---|---|
| the vault | the client's work | nothing from here, ever |
| this package | the engine | no client's rules |
| the kb folder | `kb.toml`, and what was built from it | everything this skill writes |

A knowledge base that wrote into the vault it reads would make the vault a function of its own
index. The build refuses an `--out` that resolves inside the vault.

## BUILD

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-kb/kb_build.py "<kb-folder>" --dry-run
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-kb/kb_build.py "<kb-folder>"
```

`--dry-run` first, every time, and the refusal counts are read before the real run. The dry run
selects, checks and reports; it writes nothing. A selection rule that quietly de-published half
the corpus reads exactly like a good build, and the count is the only place it shows.

Output, all of it under `<kb-folder>/kb/`: `records.jsonl` one line per citable unit,
`docs/` the source text each record came from, `index.sqlite` FTS5 plus a facet table, and
`manifest.json` naming the vault, the corpus hash, the builder hash, the counts, and every file
that was refused with the reason.

Provenance is a corpus hash over the selected file set: path, size and content digest. Not a
commit, because the vaults this reads are deliberately not in git. Same corpus hash and same
builder must mean the same bytes out.

## kb.toml

The build refuses to guess what may be answered from, so the rules are a file beside the output.

| Key | Default | What it decides |
|---|---|---|
| `vault` | none, required | the folder read. Must exist, and the output may not be inside it |
| `name` | the kb folder's name | what the report calls this base |
| `include.paths` | none | glob patterns, full-match. Nothing outside them is read |
| `exclude.paths` | none | wins over `include`, always |
| `include.status` / `exclude.status` | none | frontmatter `status:`, lower-cased |
| `granularity.clause` | `["ird"]` | `type:` values split into numbered clauses |
| `granularity.card` | none | `type:` values taken whole, one record per card |
| `chunk.max_chars` | `1800` | the cap before a unit is split or cut |
| `gates.max_shrink_pct` | `10` | how far the record count may fall before the build refuses |

`kb.example.toml` sits beside this file and is the live exemplar. A `type:` in neither
granularity list is split on its headings, which is the fallback rather than a decision.

## WHAT THE BUILD REFUSES

Each refusal names itself and prints what it found. It never exits on a number alone.

| Refusal | Why |
|---|---|
| a selected file is a cloud placeholder | reading one blocks or silently yields nothing, and a file that is not really on this disk must never become an answer |
| a record claims an anchor its document does not contain | a citation that does not resolve is worse than no citation |
| the same corpus and the same builder produced a different record count | that is non-determinism, and it makes every citation unstable. A CHANGED builder is expected to differ and is reported, not refused |
| the record count fell by more than the margin | `--allow-shrink` exists for when it is intended, and states that it was |
| no `kb.toml`, or it names no vault, or the vault is not a folder | the build will not guess a corpus |
| the output would land inside the vault | see the three homes |
| this Python has no FTS5 | there is no index without it, and a half-built kb is not offered |

## ASK

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-kb/kb_ask.py "<kb-folder>" "<question>" [--k 6] [--type ird] [--status <s>] [--exact] [--prompt] [--json]
```

**Retrieval only.** It finds the passages and formats them so an answer built on them can be
checked; it does not write the answer. Whatever writes the answer takes the block from
`--prompt`, which carries the standing rule: every claim names a record, and `Unknown` is a
correct answer.

It reads only the built `kb/`. The vault is not touched and does not need to be present.

Two honest signals in the output, both of which mean the same thing to the reader: `PARTIAL`,
where no passage carried every word of the question and the answer is probably `Unknown`, and
`Ничего не найдено`, which is itself an answer about the corpus.

## SITE

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-kb/kb_site.py "<kb-folder>" [--type ird] [--out site]
```

One self-contained HTML file: search, filters, and every clause with a citation to copy. It
embeds what it needs and opens from the disk with no server, because the answer to where
internal regulations may live was "the laptop for now". It filters only on facets the corpus
actually carries, and names the missing ones rather than showing an empty control.

## WHAT IT WILL NOT DO

**No vector store and no embeddings.** Full text over a corpus that fits on a laptop. Reopened
by a corpus that does not fit, or a recall failure someone can name: `ROADMAP.md` R-12.

**It does not write into any vault**, including the one it reads.

**It does not answer.** A retrieval that also wrote the answer would be the one component in
this package whose output nobody could check against its input.

## NOT CHECKED

Listed because a build that is quiet about its blind spots is worse than one with fewer gates.

- **Whether the selection rules select the right things.** Every gate here is mechanical. That
  `include.paths` names the documents that should be answerable is a human reading, and the
  refusal list in the manifest is where it is read.
- **Whether an answer built on the passages is correct.** Retrieval puts the evidence in front
  of a reader; nothing here judges the reasoning over it.
- **Russian stemming is a prefix cut**, three characters off a long word. It costs precision and
  buys recall, and it is the first thing to replace when the question log says retrieval is
  missing things.
- **The registry page has no access control.** It is a file on a disk, and who may hold that
  file is a decision taken outside this skill.
