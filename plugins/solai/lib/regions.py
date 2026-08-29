# -*- coding: utf-8 -*-
"""Marker-delimited regions inside a file the user owns.

    <!-- solai:begin card-index src=e019172f body=8bd86baf -->
    ...generated content...
    <!-- solai:end card-index -->

Why regions instead of hashing whole files: a vault's `CLAUDE.md` is mostly hand-written
prose with a handful of tables that must track the declarations. Hash the file and the
first paragraph the user edits freezes every table in it forever, so the user stops
running the generator. Hash the region and one dirty region costs one region.

Rules, all load-bearing:
  - A region's body hash covers the region content only, never the surrounding file.
  - Content that no longer matches its hash is HAND-EDITED: skipped, reported, never
    overwritten. The user wins inside a region too.
  - A missing region is inserted at the position the manifest declares, not wherever
    the cursor happens to be, so file order is a property of the archetype and not of
    the order the emitters happened to run in.
  - Markers are HTML comments: invisible in Obsidian's reading view, harmless in source.
"""
import re

from . import stamp

BEGIN = '<!-- solai:begin %s src=%s body=%s -->'
END = '<!-- solai:end %s -->'

# A leading `#` or `//` is tolerated so a marker can sit inside a YAML frontmatter block or a
# JavaScript file, where a bare HTML comment would be a parse error but a comment in the host
# language is not. One marker mechanism for the whole package is worth more than a tidier regex.
#
# The prefix and this regex are one unit: a projection that writes a prefix this pattern does not
# accept produces markers the ENGINE cannot find either, so its own merge stops working and every
# region reads absent. That is not hypothetical - it is what `// ` did before it was added here.
_MARK = r'^[ \t]*(?:#|//)?[ \t]*<!--[ \t]*solai:%s[ \t]+'
# src/body accept any non-space token, not just hex. A malformed stamp must still be FOUND,
# so it can be reported as malformed. A regex that only matches well-formed markers makes a
# broken one invisible, which is the worst of the three outcomes.
_BEGIN_RX = re.compile(
    (_MARK % 'begin') + r'([A-Za-z0-9_-]+)'
    r'(?:[ \t]+src=(\S*))?(?:[ \t]+body=(\S*))?[ \t]*-->[ \t]*$',
    re.M)
_END_RX_T = (_MARK % 'end') + r'%s[ \t]*-->[ \t]*$'


class Region(object):
    __slots__ = ('id', 'src', 'body', 'content', 'start', 'end')

    def __init__(self, rid, src, body, content, start, end):
        self.id, self.src, self.body = rid, src, body
        self.content = content
        self.start, self.end = start, end      # char offsets of the full block

    def verdict(self, expected_src):
        if stamp.body_sha(self.content) != (self.body or ''):
            return stamp.HAND_EDITED
        if expected_src is not None and self.src != expected_src:
            return stamp.STALE
        return stamp.CLEAN


def find_all(text):
    """-> {region_id: Region}. A begin without a matching end is skipped, not guessed at."""
    out = {}
    for m in _BEGIN_RX.finditer(text):
        rid, src, body = m.group(1), m.group(2) or '', m.group(3) or ''
        end_rx = re.compile(_END_RX_T % re.escape(rid), re.M)
        em = end_rx.search(text, m.end())
        if not em:
            continue
        content = text[m.end():em.start()].strip('\n')
        out[rid] = Region(rid, src, body, content, m.start(), em.end())
    return out


def render(rid, content, src, comment=''):
    """`comment` prefixes both markers, for a region living inside a YAML block ('# ')."""
    content = content.strip('\n')
    return '%s%s\n%s\n%s%s' % (comment, BEGIN % (rid, src, stamp.body_sha(content)),
                               content, comment, END % rid)


def replace(text, rid, content, src):
    """Replace an existing region. Raises KeyError when it is absent, never inserts blindly."""
    reg = find_all(text).get(rid)
    if reg is None:
        raise KeyError(rid)
    return text[:reg.start] + render(rid, content, src) + text[reg.end:]


def insert(text, rid, content, src, order=()):
    """Insert a missing region, honouring the declared region order.

    Placed immediately after the last region that precedes it in `order` and is present.
    With none present, or no order given, it goes at the end of the file.
    """
    if rid in find_all(text):
        return replace(text, rid, content, src)
    block = render(rid, content, src)
    present = find_all(text)
    anchor_end = None
    if order and rid in order:
        for prev in reversed(order[:list(order).index(rid)]):
            if prev in present:
                anchor_end = present[prev].end
                break
        if anchor_end is None:
            for nxt in order[list(order).index(rid) + 1:]:
                if nxt in present:
                    head = present[nxt].start
                    return text[:head] + block + '\n\n' + text[head:]
    if anchor_end is None:
        return text.rstrip('\n') + '\n\n' + block + '\n'
    return text[:anchor_end] + '\n\n' + block + text[anchor_end:]


def strip_markers(text):
    """The file as a reader sees it, markers removed. For diffs and previews only."""
    out = _BEGIN_RX.sub('', text)
    return re.sub((_MARK % 'end') + r'[A-Za-z0-9_-]+[ \t]*-->[ \t]*$', '', out, flags=re.M)
