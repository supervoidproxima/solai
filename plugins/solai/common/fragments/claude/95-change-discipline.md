## Change discipline

A change to a convention, a schema, a vocabulary, a folder structure or a skill's behaviour
is recorded **before it takes effect**, as `{changes_folder}/CHG-NNN.md`, with a body table
of Change, Reason, Impact.

What obliges a record:

| Change | Record | Also |
|---|---|---|
| New or renamed frontmatter key, tag, or status value | yes | amend `_system/vocabulary.md` |
| New card class, or a change to one's schema | yes | edit the class declaration, then regenerate |
| Folder added, renamed or retired | yes | name the fate of every artefact in it |
| Skill behaviour or output path changes | yes | update that skill's `CHANGELOG.md` |
| Fixing a typo, adding a card, writing an analysis | no | this is the work, not a change to the rules |

Retiring anything names the fate of each affected artefact from a closed set: leave,
migrate, regenerate, orphan.

A change record is immutable once written. Correcting one means writing the next one. A fix
already tried and reverted may not be proposed again without new evidence.
