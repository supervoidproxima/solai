---
name: solai-release
description: Cut a release of the solai package. Runs every gate LAST, refuses a dirty tree, then pushes, fast-forwards main and tags. Prints the vault obligation it cannot discharge itself.
scope: global
trigger_phrases:
  - "/solai release"
  - "cut a release"
  - "ship this version"
permissions:
  read: true
  write: false
  execute: true
  network: true
---

=== SOLAI - RELEASE ===

`--check` is the default and pushes nothing.

```
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-release/release.py
py ${CLAUDE_PLUGIN_ROOT}/skills/solai-release/release.py --apply
```

## THE ORDER IS THE FEATURE

Gates run **last**, immediately before the push. Not as a step earlier in the session that is
remembered as done.

On 2026-09-12 a release ran all three gates, then bumped a version, then committed. The bump
truncated `lib/__init__.py`; the package could not import; the commit went in with three green
gate results above it in the transcript. Nothing lied. The gates were green when they ran, and
then the tree changed.

A dirty working tree is refused for the same reason: an uncommitted change is a change the gates
did not see.

## WHAT IT REFUSES

Each refusal names itself. It never exits on a number alone.

| Refusal | Why |
|---|---|
| a dirty working tree | the gates would be testing a different tree |
| a tag that already exists | a released version is immutable; bump first |
| a version no CHANGELOG row claims | a release nobody wrote down cannot be read back |
| the branch is behind its target | merging is judgement, and a conflict is a decision |
| the branch is not ahead | there is nothing to release |
| any red gate | it prints the last twelve lines of the one that failed |

## WHAT IT WILL NOT DO

**It does not merge.** When `main` has commits this branch lacks, it says so and stops. Resolve
by hand, on the branch, where the gates can run over the result.

**It does not write into any vault.** A vault reads its own declarations, and this package does
not reach into one.

## WHAT IT NAMES BEFORE THE GATES

Every vault it has been pointed at and has not read since an older version, from the log that
`scaffold.py "<vault>" --harvest` writes. It prints before the gates rather than after, because
harvesting is something to do before cutting a release: a fix living in a vault is a fix this
version could have carried.

It cannot refuse on that list, and this is deliberate. The list is necessarily incomplete, since
a package cannot discover a vault nobody told it about, and a gate that fires on an incomplete
list is one people learn to pass rather than to satisfy.

## THE PART IT CANNOT DISCHARGE

After a successful release it prints the obligation rather than pretending it is done: a
deliverable card is owed `sent-on` and `status: sent`, and the change record that says what left.

A release that ships while the vault still reads `0 sent` has made the one number the whole ratio
is measured against wrong, and no amount of green gates here says anything about that.

## NOT CHECKED

Listed because a release tool that is quiet about its blind spots is worse than one with fewer.

- **Whether the release is a good idea.** Every check here is mechanical. That the version
  contains what the CHANGELOG says it contains is a human reading.
- **Whether the marketplace serves it.** The push is verified; what an installer receives
  afterwards is not.
- **Anything about a vault.** Including whether the thing being shipped can reach one.
