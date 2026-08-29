# Tiers

Three of them. The tier decides how strictly a place is governed: what its skills promise,
which assertion families run, and how change is recorded.

**It does not decide which files exist.** That is the archetype's manifest, artefact by
artefact, and a `role` place at `light` still gets its data dictionary and its validators
because `role` declares them. The table below reads as the shape each tier is *for*, not as a
filter the engine applies - it has never had one.

| | light | standard | governed |
|---|---|---|---|
| Idea | a notebook with rules it can check | a vault with a data model and change discipline | an organisation with units, powers and an impact index |
| Typically carries | `os/vault.md`, `vocabulary.md` | + `data-dictionary.md`, `state.md`, `scripts/` | + `org/charter.md`, `org/registry.md`, `org/impact.md`, `org/counsel-log.md` |
| Change records | one append-only file | one file per change | + an affects list, required |
| Skill contract | none | short `vault_contract:` | full, with unit and delegated writes |
| Assertion families | DOC VC FM LK ID GN CG AV | + ST CD JD | + OR CH IM |

Defaults: project standard, personal light, role standard, minimal light and capped there.

The tier is also the only thing the empty-folder cap negotiates with: `check_caps` refuses an
empty place more than four system files and one skill unless a first artefact is named, at
every tier, which is why a place with nothing in it cannot be handed a card system by asking
for a bigger tier.

## Promotion

Promotion is a verb, never a side effect, and it is refused unless all four hold:

1. The current tier runs with zero BLOCKERs, and every open GATE is accepted in writing in the
   bond, with a reason.
2. The counted threshold for the target tier is met, counted live and never read back from the
   bond. A file that counts itself is stale within a minute.
3. The user has seen the cost line: how many newly required fields land on how many existing
   files.
4. The user confirms.

A trigger may be reported as a proposal (over 150 content files, three or more generating
skills, two skills writing one folder, a second author committing) but a tier change is a
decision, and a decision is a change record.

## Demotion

Allowed, and it never deletes. Files move to `_system/os/_retired/<date>/` with a manifest
naming each artefact's fate: leave, migrate, regenerate, orphan.

## Governed is not the goal

Two of the four archetypes default below standard, and that is not a staging area. Fangorn
took years to earn its org layer and its own counsel log recorded the cost of reaching for it
early: 49 documents to 4 artefacts. A tier is a description of what a vault has become, not an
ambition for it.
