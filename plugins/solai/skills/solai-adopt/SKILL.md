---
name: solai-adopt
description: Read an existing Obsidian vault and report where it stands against the canon. Counts first, infers card classes from what is on disk rather than from a template, and ends with what it could not check. Writes nothing to the vault. Normally invoked by /solai adopt.
scope: global
trigger_phrases:
  - "/solai-adopt"
permissions:
  read: true
  write: true
  execute: true
  network: false
---

=== SOLAI-ADOPT - THE PROBE ===

ARGUMENTS: $ARGUMENTS
A vault path.

## The command

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-adopt/probe.py "<vault>" \
   [--json] [--report "<vault>/_system/runs/solai/YYYY-MM-DD-conformance.md"]
```

Read-only over the vault. The only file it writes is the report, and only where told.

## The nine probes

`P1` root markers · `P2` governance layer, with versions, giving the observed tier · `P3` card
classes inferred from disk · `P4` frontmatter key census, including kebab violations and
singular/plural pairs · `P5` tags in use against tags declared · `P6` change discipline ·
`P7` skills, vault-local and globally scoped · `P8` files claiming to be generated with no
stamp · `P9` any existing bond, which makes this an upgrade rather than an adoption.

Inference rules, stated so a reader can disagree with them: a key present in 95% or more of a
sample of twenty is treated as required; a scalar with eight or fewer distinct values across
ten or more cards is treated as an enum. These are proposals for declarations, not findings.

## Two rules from the report that survive into how you relay it

**Every finding carries a path, or a count of paths, or it is not a finding.** No impressions.

**Section 6 is read out.** It lists what this pass could not check and why. A summary that
drops it is claiming coverage the probe does not have, which is the failure the whole package
is built to avoid.

## Then stop

Migration is a separate, explicit act. Ask which tier to adopt, and apply the map as one
change record. Never pass anything that writes on this verb.

## RULES

- Count before judging. A verdict on an uncounted vault is an opinion about a stranger.
- Never write into the vault being probed, including "harmless" fixes.
- Relay the not-checked section. Every time.
- An inferred class is a proposal. Say so, and let the analyst correct it before it becomes a
  declaration.
