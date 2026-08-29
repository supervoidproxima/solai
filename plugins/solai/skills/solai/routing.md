# Routing

Resolve an intent to the thing that owns it. Five rules, ranked. The rank that fires *is* the
confidence: there is no separate score, because a number invented next to a rule is a way of
sounding certain without being it.

## The rules

**1. An explicit path in the intent.** "add a row to `_system/state.md`" resolves to that file.
A path match outranks everything else, including a trigger phrase that reads closer.

**2. The implied write target.** Ask what artefact this would produce or change, then match
that path against the folder map in the vault's CLAUDE.md and against each class's declared
folder. "log that the deadline is missing" implies a card in the gaps folder.

**2b. Delegated writes before ambiguity.** Where two owners' paths are both implied, check
whether one holds a declared grant to write the other's path. A grant is design, not
collision, and treating it as a conflict refuses the only mechanism that could have done the
work.

**3. A skill's declared writes.** Available only where skills carry a `vault_contract:`, which
is tier standard and above. Below that, say the rule is unavailable rather than skipping it in
silence.

**4. A trigger phrase.** Word-boundary matched, never substring. "gap" inside "gaps in the
market" is not a match.

**5. The prose remit.** Offered as a question, never as an answer. Prose is the thing the
other four rules exist to avoid relying on.

## Refusal

Four cases, each named rather than guessed through.

| Case | Response |
|---|---|
| No rule fires | Say so. List the folders that could plausibly own it. Ask which. |
| Two rules of equal rank fire | Name both candidates and the rule. Ask which. |
| The intent implies a path nothing owns | Report it as a finding. An unowned path is information, not an error. |
| The intent needs a verb that does not exist | Name the missing verb and stop. Never simulate one. |

Guessing writes into the wrong place, and a wrong write costs more than a question.
