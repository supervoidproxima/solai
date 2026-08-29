# Authoring an agent or a workflow

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
