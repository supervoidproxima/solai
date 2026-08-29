---
name: solai-scaffold
description: The deterministic vault scaffolding engine behind /solai. Renders every artefact from the class declarations, classifies what is already on disk, and writes only after a plan has been shown. Normally invoked by /solai rather than directly.
scope: global
trigger_phrases:
  - "/solai-scaffold"
permissions:
  read: true
  write: true
  execute: true
  network: false
---

=== SOLAI-SCAFFOLD - THE ENGINE ===

ARGUMENTS: $ARGUMENTS

You are almost certainly here by mistake. `/solai new` runs the interview that produces the
answers this engine needs, and this engine without those answers builds a vault nobody was
asked about. Use `/solai` unless you are debugging the engine itself.

## The command

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-scaffold/scaffold.py "<vault>" \
   --archetype <minimal|project|personal|role> \
   --answers name=<n> remit=<r> output_language=<en|ru> first_artefact=<f> [partition=A|B]
   [--materials "<file or folder>"] [--apply] [--only <artefact-id,...>]
   [--force <artefact-id>] [--rollback]
```

`--plan` is the default and writes nothing. Always show the plan table before `--apply`.

`--materials` is repeatable. Each path is a file or a folder of documents prepared for the
place; every file lands as a COPY row in the plan, in the folder the archetype declares for
unprocessed capture (`_inbox` unless a manifest says otherwise). The engine does not open
them. Deciding which of them constitutes the role and which is background is judgement, and
judgement belongs to a session with an agent in it, not to a plan that must stay a projection
of the declarations (D12). A missing path, two files with one basename, and a path inside
the place itself are all refused by name.

## What it guarantees

- **Declarations first.** If the class declarations do not hold together, nothing is written
  and every reason is named at once.
- **Idempotence.** Applying twice in a row is a no-op. This is the engine's own eval, and it
  is the only test that can falsify the design.
- **Order.** Folders, then copied runtime, then compiled declarations, then the data
  dictionary and vocabulary, then card skills, then the base, then seeded files, then
  CLAUDE.md, then the bond. CLAUDE.md is late because its generated regions read what the
  earlier steps created. The bond is last because it counts them.
- **Frozen build counts.** The bond records what the bootstrap ratio was, once. A file that
  recounts itself on every run is stale the moment it is written.
- **Rollback.** Every write records a pre-image sha and mtime in
  `_system/os/apply-manifest.json`, with a backup copy. `--rollback` restores from it.
- **Long paths.** Every path goes through the `\\?\` helper. Cyrillic under a deep OneDrive
  root breaks 260 characters routinely, and `os.*` fails opaquely when it does.

## Solai - the same engine, driven from a page

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-scaffold/serve.py [--port N] [--no-browser]
```

Prints one loopback URL carrying a key made at boot, and opens it. The page counts what is
at the path, offers the questions the chosen archetype declares, shows the plan table, and
only then lets `create` run. It is a front-end and nothing more: every plan and every apply
is a `scaffold.py` call whose output it relays whole, refusals included.

The engine, the command and this page are all called **Solai** - «just so» in Kazakh, what
you call the answer when what was declared and what was built turn out to be the same. The
split between a package name and a page name was tried and dropped: it cost a sentence of
explanation everywhere and bought nothing.

`--plan` before `--apply` stops being a habit here. The page holds a fingerprint of the
answer set the plan was shown for; editing any field voids it and `create` goes back to
unavailable, and the apply that uses a fingerprint spends it.

Not a `/solai` verb on purpose. `skills/solai/SKILL.md` is at its 200-line cap, and a verb
that squeezed in beside the others would trade a real trim for a convenience. Run the
command.

## What it refuses

An empty vault above `light`. A tier whose content threshold is unmet with no first artefact
named. A generated file that has been hand-edited. A card skill that would exceed 200 lines,
naming the region to move out.

## RULES

- Never pass `--apply` without the user having seen the plan.
- Never pass `--force` to get past a hand-edit report. Merge, or ask.
- Relay a refusal as written. Working around it silently defeats the point of having one.
