# -*- coding: utf-8 -*-
"""What a stamp on a generated HTML page is, spelled once, for the writer and the reader.

WHY THIS EXISTS. `GAP-016`. `gen_dashboard.py` hashed the page it built and printed the digest
into the footer as bare text, never using the `STAMP` constant it declared for the purpose, and
`stamp_check.py` walked `.md`, `.base` and `.js` and read no `.html` at all. So every vault this
package builds held one artefact whose integrity nothing checked, and it was the one artefact
anybody opens.

WHY ONE MODULE RATHER THAN TWO HALVES. `_args.py` and `_wikilink.py`, for the third time. A stamp
is a rule shared by whoever writes it and whoever reads it, and the two halves living apart is
what makes them drift. It is also the exact defect 0.36.1 and 0.36.2 were spent on: a value worked
out somewhere other than where it is compared. Here the two places are necessarily different
FILES, so the rule is a third file both import rather than a sentence in two docstrings asking
each side not to drift.

THE BLANKING, which is the part that is easy to get wrong and was got wrong. A file cannot
contain the hash of itself, so the digest is taken over the document with its own digest BLANKED,
by both sides alike. `gen_dashboard.py` hashed the document carrying the literal `__STAMPLINE__`
placeholder instead, which only the writer can reproduce: a reader holding the finished file has
no way back to it. Blanking is symmetric; a placeholder is not.

WHAT THE PATTERN ACCEPTS. `page=` and `inputs=` are optional, so one reader covers both the
dashboard's plain stamp and the richer stamp a site page carries, which is the shape the Counselor
vault built under its own `CHG-132` and the shape this pattern was written against.
"""
import hashlib
import re

# The stamp a generator writes, with the digest left empty. `%s` is the generator's own name.
STAMP = '<!-- solai:generated-by %s body=%s -->'

# Group 1 is everything up to and including `body=`, group 2 the digest, group 3 the tail.
# Splitting it there is what lets one expression both READ the digest and BLANK it, so the two
# operations cannot disagree about where the digest begins.
PAGE = re.compile(r'(<!--[ \t]*solai:generated-by[ \t]+\S+'
                  r'(?:[ \t]+page=\S+)?(?:[ \t]+inputs=\S*)?'
                  r'[ \t]+body=)([0-9a-f]*)([ \t]*-->)')


def norm(text):
    """The bytes both sides hash. Line endings and trailing whitespace are not content."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return '\n'.join(l.rstrip() for l in text.split('\n')).rstrip('\n') + '\n'


def blank(text):
    """The document with its own digest emptied, which is what either side can reproduce."""
    return PAGE.sub(lambda m: m.group(1) + m.group(3), text)


def body_sha(text):
    """The digest of a page, taken over the page with its digest blanked."""
    return hashlib.sha256(norm(blank(text)).encode('utf-8')).hexdigest()[:16]


def read(text):
    """-> (declared, actual) for a stamped page, or None when it carries no stamp.

    None is the honest answer for a page nobody stamped, and it is not the same claim as a
    digest that fails to match. The caller decides what an unstamped file means; this says only
    that there is no stamp to read.
    """
    m = PAGE.search(text)
    if not m:
        return None
    return m.group(2), body_sha(text)


def sign(text, generator):
    """-> the document with its stamp filled in. The one way a page is stamped.

    The text handed in must already carry the stamp with an empty digest, which is what puts the
    stamp where the generator's own template says it goes rather than where this module guesses.
    """
    if not PAGE.search(text):
        raise ValueError('%s produced a page carrying no stamp to fill in. The template must '
                         'contain `%s` before this is called.'
                         % (generator, STAMP % (generator, '')))
    digest = body_sha(text)
    return PAGE.sub(lambda m: m.group(1) + digest + m.group(3), text, count=1)
