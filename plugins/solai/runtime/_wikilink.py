# -*- coding: utf-8 -*-
"""What a wikilink is, spelled once, for everything that reads one.

WHY THIS EXISTS. `GAP-013`. Inside a Markdown table cell a bare `|` ends the cell, so Obsidian
requires the alias separator of a wikilink to be written `\\|`. Five patterns in this package
read a wikilink and none of them allowed it, so `[[subjects/SUB-028\\|Physics]]` was read as a
link to `subjects/SUB-028\\`, a file no vault contains. On one 1,769-file vault that reported
1,808 broken links where there were 8, and the failure was silent in the direction that matters:
nothing said "I could not parse these", they were reported in the same words as a genuinely
broken link.

The fix had existed in that vault's own copy of `check_links.py` for days. It reached the package
only because an upgrade overwrote the file and the count moved.

WHY ONE MODULE RATHER THAN FIVE CORRECTIONS. The same argument as `_args.py`, made again because
the evidence repeated. There the rule "the vault root is `argv[1]`" was written nine times and
had drifted twice. Here "this is what a wikilink looks like" was written five times and had
drifted once already, in the only direction that matters: the correct version was the one outside
the package.

WHAT THE TARGET CLASS EXCLUDES, and why each. `]` and `|` end the link or the target. `#` and `^`
begin an anchor, which is an address inside the note and not part of its name. `\\` is the escape
of the pipe, and excluding it is the whole fix: no target in any vault here contains a backslash,
because a path in a wikilink uses `/`.
"""
import re

# One class, two patterns built from it, so the rule cannot drift between them.
_TARGET = r'[^\]|#^\\]+'
_ANCHOR = r'(?:[#^][^\]|]*)?'
_ALIAS = r'(?:\\?\|([^\]]*))?'

# A whole link in body text. Group 1 is the target, group 2 the display alias or None.
LINK = re.compile(r'\[\[(' + _TARGET + r')' + _ANCHOR + _ALIAS + r'\]\]')
# The head of a link, for a frontmatter value, which is quoted and may not be closed on the line.
HEAD = re.compile(r'\[\[(' + _TARGET + r')')


def target(value):
    """The note a frontmatter value names, or None if it names none.

    Anchored at the start: a value that is not a wikilink is not one, and searching inside it
    would make a link out of prose that merely mentions one.
    """
    m = HEAD.match(str(value).strip())
    return m.group(1).strip() if m else None


def targets(value):
    """Every note a frontmatter value names. The value may be a list, a string, or neither.

    A plain string that holds no link is taken as a name in its own right: `related: [GAP-013]`
    without brackets is what a person writes, and reading it as nothing is how a link goes
    missing. A string that holds a broken `[[` is not, because then the name is a guess.
    """
    out = []
    for item in (value if isinstance(value, list) else [value]):
        if not isinstance(item, str):
            continue
        found = [m.group(1).strip() for m in HEAD.finditer(item)]
        if found:
            out.extend(found)
        elif '[[' not in item and item.strip():
            out.append(item.strip())
    return [o for o in out if o]
