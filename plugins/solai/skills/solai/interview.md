# The setup interview

Count first, ask least, and store the two answers that matter.

## Step 1 - count, and print it

Before a single question: files, folders, markdown with frontmatter, skills already present,
last edit date.

Print them. A tool that hands down a tier for a vault it has not counted is guessing, and the
guess always runs in the direction of more structure.

## Step 2 - name the honest tier

| Counted | Honest tier | Why |
|---|---|---|
| 0 content files | light, capped | Nothing here has been written, so nothing here has earned a schema |
| under 20, nothing named | light | A data model over twenty notes gets rewritten before it is read |
| 20+, or a named artefact with a date | standard | A model is already in use, written down or not |
| 150+ and 3+ working skills and a green standard run | governed may be discussed | Units and an impact index earn their keep at this size, not before |

Say what the next tier up would require. Do not offer it as a choice the counts do not
support: offering it implies it is reasonable.

## Step 3 - ask only what the archetype declares

Read the `asks` list from the archetype manifest. Ask those, in that order, and nothing else.
Anything absent from that list is derived, and asking for a derived value invites an answer
that contradicts the declaration.

Ask in one message, not one at a time. Offer defaults in brackets and accept "default".

## Step 4 - the two questions that are always asked

**Output language.** Reasoning stays British English. This sets what the vault produces for a
reader. It selects the label file the emitters read, so the answer is structural, not cosmetic.

**What is the first thing this vault will produce, and by when?**

Stored as `first-artefact` in the bond. It becomes the denominator of every ratio reported
from then on, and it is not a target to be moved when the number looks bad: moving it is the
failure the ratio exists to detect.

If the user will not name one, say plainly that the vault will be built at light and why, then
build it at light. Do not invent an artefact on their behalf, and do not climb to a higher
tier on the strength of an answer they declined to give.

## Step 5 - the questions by name

| Answer | Asked when | What it decides |
|---|---|---|
| `mode` | always | greenfield or adopt |
| `root` | always | the vault path; its basename becomes the name unless overridden |
| `name` | always | display name |
| `remit` | always | one line, what this vault is for. Lands in CLAUDE.md and the bond |
| `output_language` | always | the emitters' label file, and which style lexicon is copied in |
| `first_artefact` | always | the promise, and the denominator |
| `governance_tier` | archetypes with more than one | which system files exist and which assertions run |
| `classes` | project | which card classes to declare. Drop any with no work in them |
| `partition` | project | short codes for the top-level split of the domain, or blank |

## Step 6 - show the plan, then apply

Run the engine without `--apply` first, every time. Show the table. Then apply.

At the end, report the bootstrap ratio out loud and say that the next thing this vault
produces should be content. That sentence is not decoration: it is the one thing setup can do
about the failure mode setup is most likely to cause.
