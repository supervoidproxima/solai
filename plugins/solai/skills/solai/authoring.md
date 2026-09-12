# Authoring an agent, a workflow or a card class

The detail behind `/solai agent`, `/solai workflow` and `/solai check --agents`. The engine
writes; this file says what to ask before letting it.

## The order, and why it is this order

1. **Declare.** `author.py` writes one TOML into `common/agents/` or `common/workflows/` and
   appends the name to each archetype that takes it.
2. **Regenerate.** `scaffold.py <place> --apply` projects it into that place.
3. **Check.** `check_agents.py <place>` confirms it holds together and lists its evals as
   outstanding.

Never step 2 without step 1. A projection written by hand is a copy that will disagree with its
declaration on the next run, and the disagreement is always resolved in the declaration's favour,
so hand-editing one is work that gets deleted.

## `agent <name>`

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai/author.py agent <name> \
   --job "one paragraph: what it is sent to do, and what it does not do" \
   --sent-when "the moment someone should reach for it" \
   --returns "name=findings;type=list<obj>;of=where,quote,why;required=true;meaning=..." \
   --returns "name=searched;type=list<str>;required=true;meaning=..." \
   --eval "id=XX-1;asserts=what must hold;fails_when=what makes it wrong" \
   --refuse "the thing it must not do, and why that is the tempting one" \
   --induces "its own failure mode" \
   --archetype project,role
```

`--plan` is the default. Read the table, then add `--apply`.

**Ask these four before running it.** Each one has refused an agent that looked reasonable:

- **What does it return, field by field?** If the answer is "a report", stop. A return schema is
  what makes an agent checkable, and prose is the one shape nothing downstream can act on.
- **What would make its answer wrong?** That is the eval, and it needs a `fails_when` or it is a
  description of good intentions.
- **Does it write?** Almost always no. An agent that writes cards becomes a second minter of a
  prefix that already has one, so `writes = false` is the default and a writing tool alongside it
  is refused.
- **What failure does the job itself invite?** That is `induces`. The scout's is volume, the
  refuter's is contrarianism. An agent with no declared failure mode has not been thought about.

**The refusals `author.py` applies on its own:**

| Refuses when | Because |
|---|---|
| the name is taken by an agent, workflow or card class | one name, one thing; two addressable things with one name is the drift D6 forbids |
| the job overlaps an existing agent's by more than 55% of its significant words | two jobs sharing most of their words are one job with two names — sharpen it or extend the other |
| no `--returns` | an agent handing back prose cannot be checked |
| no `--eval` | it would assert a capability with nothing behind it (D1) |
| the declaration would not load | the file never reaches disk in a broken state, so the next person to run the engine does not meet a broken package |

## `workflow <name>`

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai/author.py workflow <name> \
   --goal "what finishing it means" --input "what it is given" --output "what it leaves" \
   --phase "title=Find;agent=scout;shape=pipeline;over=each dimension;carry=findings;detail=..." \
   --phase "title=Refute;agent=refuter;shape=pipeline;over=each finding;detail=..." \
   --archetype project
```

**Default every phase to `pipeline`.** A barrier makes every branch wait for the slowest, so it
is the expensive choice and it argues for itself in `barrier_because`, in prose, next to the
stage that pays for it. The loader refuses a barrier with no reason, a reason under 25
characters, and a workflow of nothing but barriers.

**`carry` is required on every phase but the last.** It names the return field whose contents
feed the next stage. Without it the next stage receives whole result objects and asks its agent
to work on `[object Object]` — and gets an answer, which is worse than failing.

A phase may only call an agent the archetype takes. The loader checks it, because otherwise the
projected script names a subagent the place does not have and the failure arrives at run time in
somebody's session rather than at load time here.

## `check --agents`

```
py <place>/_system/scripts/check_agents.py "<place>"
```

Nine structural assertions over the place's own compiled declarations, then the eval roster.

**Relay the eval roster as outstanding, and do not round it to a pass.** An eval judges an
agent's answer, so running one needs a model call and this script makes none. Reporting a score
it did not measure is the single dishonest move available here. If the user wants the evals run,
that is a session sending each agent a real input and judging the return against its
`fails_when` — a separate, explicit act, and its result belongs in a dated report.

## `class add|rename|retire <name>`

A class is declared inside an archetype, never in `common/`: there is no `common/classes` and
the engine does not look for one, so `--archetype` is required on all three operations.

Settle these before running `add`, because each is refused when missing rather than defaulted
into existence:

| Argument | What it decides |
|---|---|
| `--prefix` | the identifier prefix, uppercase letters. One prefix, one class, checked against every class in the target archetypes |
| `--folder` | where its cards live |
| `--purpose` | one sentence: what ONE card of this class is. Checked for overlap against every class already declared, the way an agent's job is |
| `--status` | `lifecycle=a,b;terminal=c;default=a`. The default falls to the first lifecycle value |
| `--field` | at least once. A class whose only content is a status is a checkbox, not a card |
| `--link` | `field=..;target=..;kind=one-way\|bidirectional\|lateral;reciprocal=..` |
| `--h2` | a required body heading, repeatable, in order |

Two things the renderer builds rather than asks for, because the validator rejects them and a
view is the one projection nobody reads until it is wrong: the view columns, which are
`file.name`, `status`, every declared name, then `tags`; and a rubric for every enum, because
an enum with no rubric is a list of words picked from by feel.

**`retire` is the operation this whole verb exists for.** It refuses while anything still
names the class and prints each hit: a sibling declaration whose link targets it, a loop step
calling its skill, the selection list, or its prefix hardcoded in a runtime checker. It does
not delete the generated skill or the cards already written. The engine reports the orphaned
skill on its next run, and the cards are evidence: what happens to them is a decision with a
change record, not a side effect of a retirement.

**`rename` touches only keys that hold a name** - `class`, `skill`, `target`, `field`,
`reciprocal`, `minted_by` - and never `meaning`, which mentions class names constantly. It
leaves `folder` alone, and it does not migrate a vault already built: those read their own
compiled declarations, so their cards keep the old key until each is migrated on its own
record.
