---
name: solai
description: Set up, audit and adopt Obsidian vaults. Interviews you, scaffolds a vault of a chosen archetype, generates its card skills into the vault's own .claude/skills/, and can read an existing vault read-only to report where it diverges. One command, several verbs.
scope: global
trigger_phrases:
  - "/solai"
  - "set up a vault"
  - "new vault"
  - "adopt this vault"
  - "audit this vault"
  - "add a card class"
permissions:
  read: true
  write: true
  execute: true
  network: false
---

=== SOLAI - THE VAULT DESK ===

ARGUMENTS: $ARGUMENTS
One verb, optional: `new` · `adopt <path>` · `check [--agents]` · `class <name>` · `agent
<name>` · `workflow <name>` · `change "<what>"` · `release` · `kb` · `route "<intent>"` · `explain`.
Bare `/solai` reports and writes nothing; `release` and `kb` live in their own skills.

Authority: **route and confirm.** Resolve, show the evidence, print the command, wait. This
skill never writes a vault artefact itself; the engine does, and only after a gate.

`${CLAUDE_PLUGIN_ROOT}` is this plugin's root. Everything below lives under it.

## STEP 0 - DISPATCH

Read the first token of `$ARGUMENTS`. Empty means `status`. An unknown verb prints the verb
list and stops; never guess which one was meant.

**Name the hat in every reply that writes**, on its own first line:

- `hat: enforce` - applying the rules as they are. Can check, route, refuse, report.
- `hat: change` - proposing an amendment. Needs a change record. Cannot approve itself.
- `hat: judge` - only ever hands off and reports a verdict verbatim.

One hat per turn. A turn that would switch hats mid-write stops and asks instead. The three
are separate because a desk that enforces, rewrites and absolves itself is a desk that
cannot be wrong.

## STEP 1 - `status` (bare `/solai`): ZERO WRITES

Find the bond at `<vault>/_system/os/vault.md`. Absent means this vault was not built by
`solai`; say so and offer `adopt`.

Then run, and report what it returns rather than describing it:

```
py <vault>/_system/scripts/validate_cards.py "<vault>"
py <vault>/_system/scripts/stamp_check.py "<vault>"
```

Report in this order: tier and archetype · BLOCKER, GATE and WARN counts · the
documents-to-artefacts ratio against the bond's `first-artefact` · waived principles with
their reasons · suppressed assertions with their dates · what the last build deferred, from
`_system/os/build.md`.

**Never answer "is this vault in good shape" with one number**, and never report a coverage
figure without its denominator. Stop there. This verb exists to be read, not acted on.

## STEP 2 - `new`

Read `${CLAUDE_PLUGIN_ROOT}/skills/solai/interview.md` and follow it exactly. In outline:

1. **Count first.** Files, folders, skills, last edit. Print the counts before asking
   anything. This package does not bootstrap a vault it has not counted.
2. Name the honest tier for that size, and say what the next tier up would require.
3. Ask only the questions the archetype declares in its `[interview].asks`. Everything else
   is derived: never ask for something the manifest already knows.
4. Two questions are always asked, whatever the archetype: the output language, and **what
   is the first thing this vault will produce, and by when**. The second is stored as
   `first-artefact` and becomes the denominator of every ratio reported from then on.
5. Show the plan. Then apply.

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-scaffold/scaffold.py "<vault>" --archetype <a> \
   --answers name=<n> remit=<r> output_language=<l> first_artefact=<f> [partition=A|B|C]
```

`--plan` is the default and writes nothing. Add `--apply` only after the user has seen the
plan table. If the engine refuses, **relay the refusal and stop**: do not work around it by
lowering the tier without saying so, and do not invent a first artefact on the user's behalf.

## STEP 3 - `adopt <path>`

Read-only until the user chooses. Never pass `--apply` on this verb.

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-adopt/probe.py "<path>" --report "<path>/_system/runs/solai/YYYY-MM-DD-conformance.md"
```

Relay the report's six sections, in its order, and hold to two rules from it. Every finding
carries a path or a count, or it is not a finding. And the report's last section, what was
**not** checked, is read out too: a conformance summary that quietly drops it is claiming
coverage the probe does not have.

Then stop and ask which tier to adopt. Applying the migration is a separate, explicit act,
and it lands as one change record.

## STEP 4 - `check [--fix]`

Runs the vault's own copies, never a reimplementation:

```
py <vault>/_system/scripts/validate_cards.py "<vault>" [--family CL,LK]
py <vault>/_system/scripts/stamp_check.py "<vault>"
py <vault>/_system/scripts/check_links.py "<vault>" [--orphans]
py <vault>/_system/scripts/check_agents.py "<vault>"        # --agents only
```

Report BLOCKER, GATE and WARN separately, then the not-enforced list verbatim.

`--fix`'s closed set is in `refusals.md`. It never touches a judgement: not a status, not a
link target, not an enum value, not a heading.

## STEP 5 - `class <name>`

A new card class is a declaration first. Since 0.23.0 it is authored, not hand-written:
read `${CLAUDE_PLUGIN_ROOT}/skills/solai/authoring.md` and follow it. `retire` refuses
while anything still names the class, and says what.

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai/author.py class add|rename|retire <name> [--apply]
```

**Refuse to create a class with no work in it.** Ask for the two or three real items that
would be its first cards. If they do not exist yet, the class does not either. Automate the
second one, never the first.

The engine rejects a declaration that does not hold together, and names every reason at
once: a duplicate prefix, a link to an undeclared class, a bidirectional link whose
reciprocal is missing on the target. Relay those reasons; do not patch around them.

## STEP 6 - `agent <name>` and `workflow <name>`

Read `${CLAUDE_PLUGIN_ROOT}/skills/solai/authoring.md` and follow it. Both verbs write a
DECLARATION only; the engine projects it after, and neither verb ever touches a projection.

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai/author.py agent|workflow <name> ... [--apply]
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-scaffold/scaffold.py "<place>" --apply
```

`authoring.md` holds the questions to settle first and the refusals the script applies. Two bind
always: **a barrier that cannot say why is a pipeline**, and an agent with no eval is refused.

`check --agents` runs `check_agents.py`; relay its evals as **outstanding**, never as a score:
judging an answer takes a model call that script does not make.

## STEP 7 - `change "<what>"`

**Never mint a number yourself.** `py <vault>/_system/scripts/mint_change.py "<vault>"
--title "<what>"` claims it by creating the file; write the body into what it names. Table of
Change, Reason, Impact; immutable once written; correcting one means writing the next.

What obliges a record is in the vault's own CLAUDE.md. Read it there rather than deciding
here, so the document and this tool cannot disagree.

## STEP 8 - `route "<intent>"`

Five ranked rules, in `${CLAUDE_PLUGIN_ROOT}/skills/solai/routing.md`. Rank one is an
explicit path in the intent; rank two is the implied write target matched against the folder
map; rank three is a skill's declared `writes:`; rank four a trigger phrase; rank five the
prose remit, which is offered as a question and never as an answer.

Report the unit or skill, the rule that fired, the evidence and the confidence. Then ask
before invoking anything.

**Refuse ambiguity by naming the candidates**, and check delegated writes before calling
something a conflict: a grant is design, not collision.

## REFUSALS

Read `${CLAUDE_PLUGIN_ROOT}/skills/solai/refusals.md` and hold to it. In short: never
write a vault artefact directly, never silence a stamp, never overwrite a hand edit,
never delete, and never call a vault healthy while anti-avoidance is red.

## SELF-EVAL

Score against `${CLAUDE_PLUGIN_ROOT}/skills/solai/EVALS.md`. The criterion that outranks the
rest: did this run create more machinery than the vault produced content since the last run?
If yes the run failed, however correct its output. This package declares
`induces: authoring-instead-of-shipping`, and its own files count on the document side of
every ratio it reports.

## RULES

- Count before building. Never bootstrap a vault that has not been counted.
- `--plan` before `--apply`, always, and the user sees the table.
- Relay a refusal; never route around it silently.
- Name the hat. One hat per turn.
- The declarations are the source of truth. A projection that disagrees is the defect.
- Doctrine is `${CLAUDE_PLUGIN_ROOT}/doctrine.md`, conventions `conventions.md`. Read, never restate.
- SKILL.md stays under 200 lines. Detail lives in the sibling files.
