# -*- coding: utf-8 -*-
"""Provenance stamps: is this generated file stale, or did somebody edit it by hand?

Two 16-hex truncated sha256 values in the frontmatter, the pattern Fangorn's
`_system/org/impact.md` already proves out:

    source-sha   over (package version, emitter id, every input path and its sha)
    body-sha     over the body this package last wrote

Four verdicts follow, and the distinction between the middle two is the entire point:

    UNSTAMPED    no stamp: not ours, or ours from before stamping
    CLEAN        both match. Re-render is a no-op
    STALE        source moved, body still ours. Safe to regenerate
    HAND-EDITED  body no longer matches its stamp. NOT safe. Report, never overwrite

Rewriting a body-sha to silence a mismatch is the worst single action available in this
package: it converts a detected defect into an undetectable one. Nothing here does it,
and `apply()` refuses unless the caller passes the body it is actually about to write.

Hashing normalises line endings and trailing whitespace, because OneDrive, Obsidian and
Windows all rewrite those without asking, and a stamp that trips on a CRLF is a stamp
nobody keeps.
"""
import hashlib
import re

from . import fm

UNSTAMPED, CLEAN, STALE, HAND_EDITED = 'UNSTAMPED', 'CLEAN', 'STALE', 'HAND-EDITED'

KEY_SOURCE = 'source-sha'
KEY_BODY = 'body-sha'
KEY_BY = 'generated-by'


def normalise(text):
    """Line endings to \\n, no trailing whitespace on any line, exactly one final newline."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [ln.rstrip() for ln in text.split('\n')]
    return '\n'.join(lines).rstrip('\n') + '\n'


def strip_volatile(text, patterns):
    """Remove matching lines, AND anything indented under them, before hashing.

    Obsidian rewrites `columnSize:` into every `.base` file it opens, as a key with an
    indented block beneath it. Dropping the key line alone would leave the block, so the
    file would still read HAND-EDITED on the second run, on the most visible artefact in
    the vault. The block goes with its key.
    """
    if not patterns:
        return text
    rx = [re.compile(p) for p in patterns]
    lines = text.split('\n')
    keep, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if any(r.search(ln) for r in rx):
            indent = len(ln) - len(ln.lstrip())
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                    break
                i += 1
            continue
        keep.append(ln)
        i += 1
    return '\n'.join(keep)


def sha(text):
    return hashlib.sha256(normalise(text).encode('utf-8')).hexdigest()[:16]


def file_sha(path):
    import io
    try:
        with io.open(path, encoding='utf-8') as fh:
            return sha(fh.read())
    except (OSError, UnicodeDecodeError):
        return None


def source_sha(package_version, emitter, inputs):
    """inputs: iterable of (identifier, sha) pairs. Order-independent by construction."""
    parts = ['v=%s' % package_version, 'e=%s' % emitter]
    parts += sorted('%s=%s' % (k, v) for k, v in inputs)
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:16]


def body_sha(body, volatile=None):
    return sha(strip_volatile(body, volatile))


# --------------------------------------------------------------------------- verdicts

def read(text):
    """-> dict(stamped, source_sha, body_sha, body, meta, fm_text)."""
    meta, fm_text, body = fm.load(text)
    return {
        'meta': meta,
        'fm_text': fm_text,
        'body': body,
        'source_sha': fm.get(meta, KEY_SOURCE),
        'body_sha': fm.get(meta, KEY_BODY),
        'stamped': bool(fm.get(meta, KEY_SOURCE) and fm.get(meta, KEY_BODY)),
    }


def verdict(text, expected_source_sha, volatile=None):
    st = read(text)
    if not st['stamped']:
        return UNSTAMPED
    if body_sha(st['body'], volatile) != st['body_sha']:
        return HAND_EDITED
    if expected_source_sha is not None and st['source_sha'] != expected_source_sha:
        return STALE
    return CLEAN


def apply(fm_text, body, source_sha_value, generated_by, volatile=None):
    """Return the frontmatter text carrying stamps for the body ABOUT TO BE WRITTEN.

    The body is passed in rather than read back, so the stamp can only ever describe
    bytes the caller is committing to write in the same operation.
    """
    return fm.patch(fm_text, {
        KEY_BY: generated_by,
        KEY_SOURCE: source_sha_value,
        KEY_BODY: body_sha(body, volatile),
    })


def stamped_text(fm_text, body, source_sha_value, generated_by, volatile=None):
    """Full file text with a correct stamp. The only sanctioned way to emit one."""
    body = normalise(body)
    return fm.join(apply(fm_text, body, source_sha_value, generated_by, volatile), body)
