# solai

Set up, audit and adopt Obsidian vaults from one command. This repository is also the
installer: on a Windows machine with nothing on it, one line gets you from bare Windows to a
working vault.

## Install, on a machine with nothing

```powershell
irm https://raw.githubusercontent.com/OWNER/solai/main/install.ps1 | iex
```

That installs Git, Python, Obsidian and Claude Code, registers this package as a plugin, and
opens a guided page that walks you to a first vault. It asks before each stage, installs nothing
twice, and prints what is left for you to do by hand.

To see what it would do without doing any of it:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/OWNER/solai/main/install.ps1))) -DryRun
```

## Install, on a machine you already work on

```
/plugin marketplace add OWNER/solai
/plugin install solai@solai
```

Then `/solai`. Upgrades come from `/plugin marketplace update solai`.

## What it needs

| | |
|---|---|
| Windows | 10 1809+ or 11. The installer is PowerShell and uses winget |
| Python | 3.11 or newer. The engine reads its declarations with `tomllib` |
| Git | recommended, not required by the engine |
| Node | not required by anything here |

Nothing is installed with `pip`. The engine is standard library only.

## The one idea

**Declarations are TOML. Projections are Markdown. Nothing is both.**

A card class is declared once, in one file. Five things are generated from it and none of them
is authoritative:

```
archetypes/project/classes/gap.toml
  -> _system/data-dictionary.md    status matrix, enums, schema table, link rules
  -> CLAUDE.md                     card-index region: routing only, never a field name
  -> .claude/skills/gap/SKILL.md   a working /gap command, in the vault
  -> registry.base                 one Obsidian view
  -> validate_cards.py             reads the TOML at runtime; assertions are data, not codegen
```

One 130-line declaration replaces roughly 900 lines of hand-maintained Markdown across five
files, and makes their divergence impossible rather than a discipline problem.

## What a built vault owes this package

Nothing. The runtime scripts are copied into the vault and read the declarations that sit inside
it, so a vault keeps validating itself if this package is uninstalled or three versions ahead.

More in [`plugins/solai/README.md`](plugins/solai/README.md), the principles in
[`doctrine.md`](plugins/solai/doctrine.md), and the conventions in
[`conventions.md`](plugins/solai/conventions.md).

## Licence

MIT. See [LICENSE](LICENSE).
