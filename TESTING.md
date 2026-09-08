# Testing solai

Three instruments, because "does it work" and "is it intuitive" are different questions and
only one of them can be automated. Written 2026-08-29 at v0.19.2, as a handoff: a session that
knows nothing about this conversation should be able to continue from here.

---

## What is gated today

| Command | Covers | Size |
|---|---|---|
| `py tests/run_tests.py` | The package: primitives, declarations, agents, workflows, authoring, the surface | 239 assertions |
| `py tests/verify_engine.py` | Four kinds scaffolded, applied, re-planned, checked, then probed with a real hand edit | NOOP 6 / 42 / 30 / 34 |
| `py tests/verify_install.py` | `install.ps1`: stage 0, the helpers, the promise that a dry run writes nothing, strict-mode hazards | 17 assertions |

The runner refuses a run whose assertion count does not match its declaration, so a deleted
assertion fails as loudly as a broken one.

**What none of them prove.** No stage of the installer past stage 0 has ever executed under
test. No agent eval has been run. No workflow has made a model call. And nobody who has not
built this has ever tried to use it.

---

## Instrument 1: machine tests <sub>done</sub>

`tests/verify_install.py` is new and is the first gate the installer has ever had. It is a
separate command on purpose: `install.ps1` sits at the repository root, outside the plugin, so
a marketplace install does not carry it, and folding it into the 239 would make that number
depend on a file that is legitimately absent half the time.

**Why it is safe to run.** Every invocation passes `-DryRun`, which returns at stage 0 before
anything is installed, fetched or written. The helper functions are defined above that return,
so dot-sourcing defines them and then stops — which is how `Invoke-Native` and `Have` are
tested against the real definitions rather than a copy.

**How a bare machine is simulated.** Stage 0 derives every path from `USERPROFILE` and
resolves every tool through `PATH`. Point both at an empty temp directory, clear the OneDrive
variables, and the script sees a machine with nothing on it. That technique already found four
defects by hand; these assertions are the ones that find them again.

All sixteen were mutation-tested before being kept:

| Mutation | Went red |
|---|---|
| `Invoke-Native` stops neutralising the error | `IN-14` — and note it did **not** crash. It reported exit 1 instead of exit 3, which is how `1602` would stop being recognised |
| The stage total drifts from the documented eight | `IN-03` |
| The dry run stops promising it wrote nothing | `IN-06` |

**Rule for whoever extends this: never run `install.ps1` in a test without `-DryRun`.** Stage 2
fetches and installs Claude Code for real.

---

## Instrument 2: the bare machine <sub>outstanding, needs hardware</sub>

**It cannot be done on this machine.** No administrator rights, so Windows Sandbox and Hyper-V
cannot be enabled; no Docker, VirtualBox, Vagrant, QEMU or multipass; `wsl` exists with no
distro, and WSL is Linux, which is the wrong operating system for a PowerShell installer.

Options, cheapest first: the next Windows machine you are handed, a reinstalled laptop, a
colleague's machine, or a fresh Windows VM from any cloud provider. Windows Sandbox becomes
the best option the moment someone has admin on any machine, because it resets on close.

### Protocol

1. **Dry line first, before anything else.** Every row should read `missing`. That is the
   state no run has ever been observed in, and confirming it is half the value of the exercise.

   ```
   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/supervoidproxima/solai/main/install.ps1))) -DryRun
   ```

2. **Then the real line**, and stay at the keyboard. Four stops need a person: the elevation
   prompt, the GitHub sign-in, the OneDrive sign-in, the Claude Code login. Three of the four
   can open *behind* the terminal, which is what a stalled run usually turns out to be.

3. **Check three things, in this order.** `claude plugin list` names `solai`; the doctor stage
   reported 239/239; the guided page opened in a browser.

4. **Read the summary.** A clean run ends `Nothing is left for you to do by hand`.

**The real output of this test is the numbered list of what the script could not finish, not a
pass or a fail.** Copy it back verbatim. A run that completes tells you less than a run that
names three things it could not do.

---

## Instrument 3: is it intuitive <sub>outstanding, needs a person</sub>

This cannot be automated and it cannot be answered by the person who built it. The operative
definition:

> Can somebody who has never seen this get from the one line to a first card without asking
> anyone a question?

### Protocol

Recruit one or two people. One is enough to find the worst problem; the second tells you
whether the first was unlucky. Give them exactly one sentence of context — *this sets up a
folder for keeping track of what a role owes* — then hand them the line and stop talking.

**Do not help.** The instinct to rescue is the thing that destroys the test. If they ask, write
the question down and say you want to see what they would do alone. Time-box to 30 minutes and
stop when they get there or give up; both are results.

### Where to watch

Say nothing at these moments. Just record what happens.

**During install**

- Do they open Terminal, or Command Prompt? The line is PowerShell-only and the page says so;
  if they get this wrong, the page said it in the wrong place.
- When nothing happens for a minute, do they find the elevation dialog, or wait?
- At the private-configuration question, do they know whether to answer `y`?

**At the surface**

- Does the word **kind** mean anything to them, or do they hesitate over it?
- Do they understand what **Purpose** is for, or do they type a title?
- Do they press **Review** before hunting for **Create**? If they look for Create first, the
  gate is doing its job but the page is not explaining itself.
- Do the three unavailable kinds reassure them or confuse them? This was a deliberate choice
  and it deserves a real reaction.
- Do they understand what **materials** are, and that the files are copied but not read?

**After create**

- Do they know what to do next, or does the completion panel leave them stranded?
- Does the session that opens make sense, or is the opening message noise to them?
- Do they get to a first card at all? Nobody has, including the author.

### What to record

For each moment: how long they hesitated, what they said aloud, what they tried first, and
whether they recovered alone. Hesitation over ten seconds is a finding even when they get it
right in the end.

**Their confusion is data, not a bug report.** The temptation is to explain why they were
wrong. The useful move is to write down what they expected instead.

---

## Traps

- **Never run the installer without `-DryRun` in a test.** Stage 2 installs Claude Code for real.
- **Restore `install.ps1` after mutation testing**, and check the hash. Mutations were applied
  with `sed -i` against the live file; a crashed run leaves it mutated.
- **The package is 94 files**, not 96. A count including `__pycache__` is wrong and has already
  reached a published page once.
- **`SMP` holds zero cards.** Any claim that the loop has been walked is false until
  `obligations/` has something in it.
- **The published page is edited from more than one session.** Re-read before republishing or
  the other session's work is overwritten.

---

## The order that matters

Instrument 2 proves the thing installs. Instrument 3 proves it can be used. Neither one moves
the gate the package actually reports:

```
WARN  AV-1  system 11 to content 2. Machinery is outpacing the work it exists to serve
```

Writing the first card moves that. A test plan does not, and this file is on the document side
of the ratio it is describing.
