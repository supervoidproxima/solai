# Conventions

Naming, frontmatter and operating rules for vaults built by `solai`. Supplements
`~/.claude/vault-conventions.md`, which stays the cross-vault canon; where the two differ,
this file wins **for vaults that carry a `_system/os/vault.md` bond**, and the divergence is
listed at the bottom so nobody has to discover it by collision.

---

## 1. File and folder names are kebab-case

One rule, everywhere, no exceptions by file type:

    lowercase, words joined by a single hyphen, no spaces, no underscores, no capitals

| Kind | Form | Example |
|---|---|---|
| Dated note | `YYYY-MM-DD-slug.md` | `2026-08-27-budget-cycle-review.md` |
| Undated note | `slug.md` | `budget-cycle-review.md` |
| Card | `PREFIX-NNN.md`, bare ID, no slug | `GAP-001.md` |
| Change record | `CHG-NNN.md` | `CHG-014.md` |
| Folder | `slug/` | `registry/`, `card-classes/` |
| Infrastructure folder | `_slug/` | `_system/`, `_inbox/` |
| Frontmatter key | `kebab-case` | `demand-voices`, `req-type` |
| Tag | `kebab-case` | `budget-cycle`, `cross-process` |
| Generated artefact | same rule, plus a stamp | `registry.base`, `dashboard.html` |

The date prefix uses the same hyphen as the rest of the name, so `2026-08-27-note-name.md`
is one uninterrupted kebab string. That is deliberate: a single tokenising rule means sorting,
globbing, URL-safety and tab-completion all behave, and no script needs to know where the
date stops and the title starts (it is always the first ten characters).

Cyrillic, spaces and mixed case are not used in filenames even where the content is Russian.
The human-readable title lives in frontmatter `title:` and in the `aliases:` list, so
renaming a document never breaks a wikilink. Wikilinks target the ID or the slug.

**What this diverges from.** `~/.claude/vault-conventions.md` mandates sentence case with
spaces (`Strategic planning.md`), and both existing vaults follow it. `solai`-built vaults
override that rule under D14: the displaced rule is named here, and existing vaults are
not touched.

---

## 2. Frontmatter

Minimum on every content file: `date`, `type`. Cards add `id` and `status`.

`date` is unquoted ISO `YYYY-MM-DD`. Values that are wikilinks are quoted. List fields are
present as `[]` rather than omitted, so a missing value is distinguishable from an unset one.
Key names come from the vault's closed key vocabulary, and a new key is an amendment to it
plus a change record (D6).

---

## 3. Handoff at half context

Every generated `CLAUDE.md` carries this rule, and it is not optional:

> **At roughly 50% context consumption, stop and offer a handoff.** Do not wait for the
> window to run short. Summarise state, the numbered next steps, decisions taken, open
> questions and known traps into `_system/handoff/YYYY-MM-DD-topic.md`, and give the user
> a paste-ready block for the next window. Offer it once, act on the answer, and carry on
> if declined.

Half is the bar rather than three-quarters because a handoff written under pressure is
written from a context already too full to summarise itself accurately, which is the exact
moment the summary matters. The handoff note is a normal dated kebab note and follows §1.

---

## 4. Every vault gets a dashboard

`dashboard.html` at the vault root: one self-contained file, no build step, no external
requests, opens on a double click. It carries a file explorer over the vault and whatever
per-archetype panels the vault has earned.

It is **generated and stamped** (D10). The index is embedded at generation time rather than
fetched, because browsers block `fetch()` against `file://` and a dashboard that only works
under a web server is a dashboard nobody opens. Regenerate with:

    py _system/scripts/gen_dashboard.py <vault-root>

Deliberately thin in v1: a tree, a search box, counts by `type:`, and the vault bond's
headline numbers. Panels get added as the vault produces things worth showing. A dashboard
built before there is anything to show is the failure D16 names, so it starts small and
grows against real content.

---

## 5. Markdown

- Blank lines separate paragraphs only.
- No blank line between a heading and the content under it.
- No blank lines between consecutive list items.
- No em-dashes or en-dashes as sentence continuation. Commas, colons, parentheses or a
  sentence break instead. Hyphens in compound words are fine.

---

## 6. Divergences from `~/.claude/vault-conventions.md`, in full

| Rule there | Rule here | Why |
|---|---|---|
| Note titles in sentence case with spaces | Kebab-case, optional ISO date prefix | One tokenising rule for sorting, globbing and completion; no spaces in paths |
| `date` as quoted `"YYYYMMDDHHmm"` | Unquoted ISO `YYYY-MM-DD` | Obsidian's date type and Base date filters need ISO. Fangorn already carries this override |
| Templates seeded from `~/.claude/templates/` | Templates come from the archetype | The archetype knows what its notes look like; a global template does not |

Everything else in that file, notably the hyphenated property-key rule, the `_` prefix for
infrastructure folders and the markdown formatting rules, is inherited unchanged.
