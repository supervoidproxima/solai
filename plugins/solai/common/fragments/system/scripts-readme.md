---
date: 2026-01-01
type: reference
title: "Scripts"
tags: []
---
# Scripts

What runs here, in what order, and what each one refuses to do. Seeded once by `solai` and
yours from now on: every script this vault grows gets a row, or the order stops being a
contract and becomes a thing one person remembers.

`CLAUDE.md` says this folder holds "generators and checks, with a run-order contract in the
readme". This is that contract. The first vault built on this package went five days without
one and wrote its own on the day a fold ran in the wrong order and 119 of 154 documents lost
the cohort they belonged to.

## The convention every script here follows

**The vault root is `argv[1]`, and nothing writes without `--write`.** A dry run is therefore
always safe, and "what would this do" is answerable without a backup. A script that writes by
default is the one nobody runs twice.

A **generator** owns its output completely: it may be deleted and rebuilt, and anything
hand-added to its output is lost on the next run. A **check** writes nothing and exits
non-zero on the one condition it is named for. Nothing in this folder deletes a file (D19):
a script may propose a deletion, and releasing it is a person's own act.

## Shipped with the vault

| Script | Kind | Run it | What it answers |
|---|---|---|---|
| `validate_cards.py` | check | after any card edit | do the cards match their own declarations |
| `check_links.py` | check | after any rename or move | is any wikilink broken, and what is reachable through nothing |
| `check_binaries.py` | check | after onboarding documents | is every binary described by exactly one note |
| `stamp_check.py` | check | after any engine run | has a generated region been hand-edited |
| `check_agents.py` | check | after editing an agent | does every agent declare a return schema and an eval |
| `measure_cards.py` | report | before cutting a card down | how long the cards in one folder actually are |
| `gen_dashboard.py` | generator | **last, always** | the one page that shows the vault to a person |

`gen_dashboard.py` runs last because it reflects the vault *after* everything else has run.
Running it earlier produces a picture of a vault that no longer exists by the time anyone
opens it.

## What this vault added

One row per script written here, with what it must run after and why. Add the row in the same
change that adds the script.

| Script | Kind | Runs after | Why that order |
|---|---|---|---|
| | | | |

## Orderings that bind

A dependency is written here the first time it costs something, with the cost. An ordering
nobody can explain is one somebody will "simplify" away.

| Before | After | What goes wrong otherwise |
|---|---|---|
| everything else | `gen_dashboard.py` | the dashboard shows the vault as it was, not as it is |
