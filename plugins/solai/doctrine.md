# Doctrine

The durable principles behind every vault this package builds. Distilled from two vaults
that learned them the expensive way: `Fangorn` (a personal life-OS that grew a
constitution, an org chart and an adversarial judge) and a consulting project vault
(which grew card registries, closed vocabularies and a verification constitution).

D19 came later and from a different place: the first vault this package built, five days
into running, having destroyed documents it could not get back.

**This file ships with the package and is never copied into a vault.** A vault holds only
principle IDs and its waivers. That way a doctrine change can never conflict with local
content: the worst case is a waiver pointing at a principle that no longer exists, which
is an assertion, not a merge.

**Rank.** `CORE` applies at every tier and every archetype. `TIERED` activates at a named
tier. `ARCHETYPE` is opt-in. A vault may not edit doctrine; it may waive a principle in
`_system/os/vault.md` with a reason, a date and a change record. A waiver is reported by
`solai` status forever, and waiving a CORE principle also raises a permanent warning.
That asymmetry is the whole point of the ranking.

---

| ID | Principle | The failure it prevents | Origin | Rank |
|---|---|---|---|---|
| **D1** | **Nothing may assert what it cannot show.** A contract that declares a capability with no assertion behind it says `NOT ENFORCED` in the open, naming the field. A finding without `file:line` or a quote is not a finding. A deferred step is recorded as deferred. | Machinery that implies coverage it does not have; an undeclared deferral quietly becoming a permanent hole. | Fangorn law 1, NIS zero-hallucination rule | CORE |
| **D2** | **State lives in a field; prose is commentary.** A generator reads `status:`, never a sentence. A new state is a new value of an existing field, never a new field. A terminal state carries a visible callout with its reason and date. | A card leaves the perimeter in frontmatter while the prose and every aggregate keep citing it. Happened twice in NIS, recorded as CHG-146 and CHG-154. | Fangorn law 3, NIS status protocol | CORE |
| **D3** | **Edges are authored once; both directions read one table.** A reciprocal is computed, never maintained by hand. Where a mirror is genuinely needed, the schema marks the pair and a check compares them. | Two copies of one fact with nothing comparing them. | Fangorn law 2, NIS link validator | CORE |
| **D4** | **Ownership is of paths, never topics.** Topics overlap and paths do not, so ownership of a path is decidable and ownership of a topic is an argument. Overlap is resolved by an exclusion, never by sharing. | Two skills writing one folder, each believing it is the owner. | Fangorn registry | TIERED (standard) |
| **D5** | **Claiming is not governing, and the baseline reports both.** Three buckets: claimed, unowned, out of scope. The out-of-scope bucket is enumerated by name, never pattern-matched, so it cannot quietly grow. Coverage is three numbers, never one. | A validator reporting completeness the vault does not have. | Fangorn charter Part 1 | TIERED (standard) |
| **D6** | **Every set is closed and versioned.** Tags, frontmatter keys, status values, failure modes, artefact fates. A new value is an amendment to the list plus a change record, never a judgement made in flight. | Vocabulary drift: 21 tags becoming 60, and a "new kind" that is actually an error. | NIS `TAGS.md` and `PROPERTIES.md`, Fangorn retirement fates | CORE |
| **D7** | **A rule change is recorded before it takes effect, and the record is the amendment instrument.** Retirement is a change, and its record names the fate of every affected artefact from the closed set: leave, migrate, regenerate, orphan. A fix already tried and reverted may not be re-proposed without new evidence. | Undocumented convention changes; deleting a producer and orphaning its data; the same bad idea returning every quarter. | Both vaults, 226 and 23 change records | CORE |
| **D8** | **A judgement log is append-only.** A verdict that turned out wrong is answered by the next verdict, never by a correction to this one. Its writer holds sole authority and is not the thing being judged. | Retroactively softening an uncomfortable record. | Fangorn counsel log | TIERED (standard) |
| **D9** | **Resolve by declaration, never by filename or date.** The live thing is found by `type:` plus `status: active`, not by the newest file. A dated path inside a skill's step logic is an assertion failure. | Silent staleness when a new dated file appears and half the readers still point at the old one. Fangorn produced five strategy versions in fifteen weeks this way. | Fangorn strategy contract | CORE |
| **D10** | **Generated is generated, and the file can prove it.** A generated artefact carries `source-sha` and `body-sha`; the check distinguishes STALE (a source moved) from HAND-EDITED (the body no longer matches its stamp). A hand edit is a defect, not a shortcut. | The hand-tuned artefact lost on the next regeneration, and the manual exclusion rule that goes with it. | Fangorn impact index | CORE |
| **D11** | **Direction of truth is one-way, and verification runs upwards.** Source, then card, then synthesis, then deliverable. A deliverable disagreeing with a card is a defect of the deliverable until proven otherwise. Findings above a declared severity go to a second reader tasked to refute, not to confirm. A dispute the two cannot settle goes to a human, never auto-resolved. | A number in the report that no card produces; a verification run that confirms what it set out to confirm. | NIS verification constitution | TIERED (standard) |
| **D12** | **Judgement at extraction, mechanics at render.** Structural decisions are made once, in a human-checkable table against the source; the generator is a projection with no inference. | Runtime classification bleeding into output: 50% error rate per unit and thirteen reactive patches, the recorded history of NIS CHG-095. | NIS policy | ARCHETYPE (any vault with a loop) |
| **D13** | **Silence is recorded, never carried over.** A node with no evidence gets the verdict `not-surveyed`. A unit with no probe reports `no probe`. An unenforced field says so. Absence is a value. | The most dangerous default: unexamined things quietly inheriting the status of examined ones. | NIS practice layer, Fangorn `due` | CORE |
| **D14** | **A lower charter adds; to override it must name the rule it displaces.** Inheritance is by directory and needs no machinery. An override without a named target is not an override. | Silent contradiction between a global rule and a folder-level one, with no way to tell which won. | Fangorn reporting line | TIERED (standard) |
| **D15** | **Separation of powers: enforce, change, judge. No one holds two.** Enforcement applies rules as they are. Change happens through evidence with a version bump. Judgement decides whether either is avoidance, and may rule against the enforcer. | The system marking its own homework. | Fangorn charter Part 1 | TIERED (governed); below that it degrades to a disclosure rule, which is still mechanically checkable |
| **D16** | **Machinery is not progress, and the ratio is published.** Documents authored against artefacts shipped, over a window, against a declared bar. A tool's own output counts on the document side of the ratio it reports and may not be argued out of that column. | The pathology both source vaults exhibited. Fangorn's own verdict, computed not felt: 49 documents to 4 artefacts. | Fangorn counsel | CORE |
| **D17** | **Refuse ambiguity by naming the candidates.** A router that guesses writes into the wrong place. A refusal states the case, lists the candidates, and asks the one question that resolves it. Check the delegations before declaring a conflict: a grant is design, not collision. | Writing into the wrong owner's files, or refusing the only mechanism that could have moved the work. | Fangorn routing | CORE |
| **D18** | **A stranger orients in five minutes, and every artefact type names a live exemplar.** One file answers what is canon, what is decided, what is next, and points at a real example per class. Its own update triggers are enumerated inside it. | Conventions re-derived from scratch each session, then re-derived differently. | NIS `STATE.md` and `DATA-MAP.md` | CORE |
| **D19** | **Nothing is deleted by a script, and release is a person's own act.** Copy to a holding place, verify both ends by hash, and let the holder release it. Test the copy, not the name: a size, a filename or a type is evidence about a file, never a substitute for opening it. Selection for deletion runs on per-file evidence, never on a field that describes what a file is ABOUT rather than how many things it covers. | Irreversible loss dressed as tidying. In one vault a size comparison rather than an open declared a recoverable year lost, 139 bytes apart; a bulk rule read a subject field as a scope field and destroyed twelve documents, nine with no copy anywhere, six of them held back that same day for the postholder; and of 312 files sent to trash, 199 ceased to exist anywhere. | CORE |

**Core, and therefore present even in a minimal vault (12):** D1, D2, D3, D6, D7, D9, D10, D13, D16, D17, D18, D19. Each is cheap, and each prevents a failure that costs more than the rule.

D19 is the only one added from a vault that was running rather than from one being read. It is CORE because it is the one principle here whose failure cannot be answered by the next change record: everything else in this table protects a claim, and D19 protects the evidence.

---

## Waiver format

In `_system/os/vault.md`:

```yaml
principles-waived:
  - id: D11
    reason: "No deliverable layer. Nothing sits above a note."
    date: 2026-08-27
    change: CHG-004
```

Checked by `DOC-4`: the ID must be real, and all three of reason, date and change must be present. A waiver without a reason is not a decision, it is a hole.
