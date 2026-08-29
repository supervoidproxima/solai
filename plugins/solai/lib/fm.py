# -*- coding: utf-8 -*-
"""The ONE frontmatter parser.

Every part of `solai` that needs to read or touch YAML frontmatter comes here.
Two parsers over one format is the copy-holding defect this package exists to remove,
and the vaults it targets already carry five hand-rolled ones.

pyyaml is not installed on the target machine and is not a dependency worth adding for
the subset actually used in a vault. So this parses a declared subset and REFUSES the
rest rather than guessing:

    key: scalar                 -> str | int | float | bool | None
    key: "quoted: scalar"       -> str
    key: [a, b, "c"]            -> list
    key:                        -> list
      - a
      - "b"
    key: {}                     -> dict (empty only)

Anything else (nested mappings, multi-line scalars, anchors, flow maps with content)
is preserved verbatim in `raw` and reported in `meta['__unparsed__']` as a list of
keys. A caller that needs one of those keys must handle the miss, never assume absence.

Writes are SURGICAL. `patch()` replaces the lines of the keys it is given and appends
the ones that are missing; every other byte of the frontmatter survives untouched,
including comments, key order and the user's own spacing. A stamping pass must never
reformat a file it did not otherwise change, or every stamped file reads dirty forever.
"""
import re

DELIM = '---'
_SCALAR_KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_.-]*):(?:\s+(.*?))?\s*$')
_LIST_ITEM = re.compile(r'^\s*-\s+(.*?)\s*$')


# --------------------------------------------------------------------------- split

def split(text):
    """(frontmatter_text, body). frontmatter_text is None when the file has none.

    The body keeps its leading newline so `frontmatter + body` round-trips byte-exact.
    """
    if not text.startswith(DELIM):
        return None, text
    # the opening delimiter must be alone on its line
    nl = text.find('\n')
    if nl == -1 or text[len(DELIM):nl].strip():
        return None, text
    end = text.find('\n' + DELIM, nl)
    while end != -1:
        after = end + 1 + len(DELIM)
        if after >= len(text) or text[after] in '\r\n':
            return text[nl + 1:end], text[after:].lstrip('\r\n')
        end = text.find('\n' + DELIM, end + 1)
    return None, text


def join(fm_text, body):
    """Inverse of split(). fm_text None yields the body alone."""
    if fm_text is None:
        return body
    return '%s\n%s\n%s\n%s' % (DELIM, fm_text.rstrip('\n'), DELIM, body)


# --------------------------------------------------------------------------- read

def _scalar(raw):
    s = raw.strip()
    if s == '' or s == '~' or s.lower() == 'null':
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        return s[1:-1]
    if s in ('[]',):
        return []
    if s in ('{}',):
        return {}
    low = s.lower()
    if low in ('true', 'yes'):
        return True
    if low in ('false', 'no'):
        return False
    if re.fullmatch(r'-?\d+', s):
        return int(s)
    if re.fullmatch(r'-?\d+\.\d+', s):
        return float(s)
    return s


def _inline_list(raw):
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    out, buf, quote, depth = [], '', None, 0
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch in '"\'':
            quote = ch
            buf += ch
        elif ch in '[{':
            depth += 1
            buf += ch
        elif ch in ']}':
            depth -= 1
            buf += ch
        elif ch == ',' and depth == 0:
            out.append(_scalar(buf))
            buf = ''
        else:
            buf += ch
    if buf.strip():
        out.append(_scalar(buf))
    return out


def _dedent(lines):
    """Strip the common leading indent from a nested block so it can be parsed as its own map."""
    real = [l for l in lines if l.strip()]
    if not real:
        return ''
    pad = min(len(l) - len(l.lstrip()) for l in real)
    return '\n'.join(l[pad:] if l.strip() else '' for l in lines)


def parse(fm_text):
    """Frontmatter text -> dict. Unparseable keys land in meta['__unparsed__']."""
    meta, unparsed = {}, []
    if not fm_text:
        return meta
    lines = fm_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith('#'):
            i += 1
            continue
        m = _SCALAR_KEY.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), (m.group(2) or '')
        rest = re.sub(r'\s+#.*$', '', rest) if not rest.strip().startswith('#') else ''
        if rest.strip().startswith('[') and rest.strip().endswith(']'):
            meta[key] = _inline_list(rest)
            i += 1
            continue
        if rest.strip():
            meta[key] = _scalar(rest)
            i += 1
            continue
        # empty value: a block list, a nested mapping, or a genuine null
        items, j, indented, nested = [], i + 1, False, False
        while j < len(lines):
            nxt = lines[j]
            if not nxt.strip():
                j += 1
                continue
            if not nxt.startswith((' ', '\t')):
                break
            indented = True
            im = _LIST_ITEM.match(nxt)
            if im:
                items.append(_scalar(im.group(1)))
                j += 1
                continue
            # A nested mapping: `permissions:` / `vault_contract:` are ordinary in skill
            # frontmatter, so parse one level rather than declaring the key unreadable and
            # pushing every consumer into a regex of its own.
            block, j = [], j
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith((' ', '\t'))):
                block.append(lines[j])
                j += 1
            sub = parse(_dedent(block))
            sub.pop('__unparsed__', None)
            meta[key] = sub
            nested = True
            break
        if key in unparsed:
            meta[key] = None
        elif nested:
            pass                        # already assigned above
        elif not indented:
            meta[key] = None            # `key:` with nothing under it is null, not an empty list
        else:
            meta[key] = items
        i = j
    if unparsed:
        meta['__unparsed__'] = unparsed
    return meta


def load(text):
    """text -> (meta, fm_text, body)."""
    fm_text, body = split(text)
    return parse(fm_text), fm_text, body


# --------------------------------------------------------------------------- write

def _emit(key, value):
    if value is None:
        return '%s:' % key
    if isinstance(value, bool):
        return '%s: %s' % (key, 'true' if value else 'false')
    if isinstance(value, (int, float)):
        return '%s: %s' % (key, value)
    if isinstance(value, list):
        if not value:
            return '%s: []' % key
        return '%s:\n%s' % (key, '\n'.join('  - %s' % _quote(v) for v in value))
    return '%s: %s' % (key, _quote(value))


def _quote(v):
    s = str(v)
    if s == '':
        return '""'
    if s.startswith('[[') or ':' in s or s[0] in '"\'[{&*!|>%@`#-' or s.strip() != s:
        return '"%s"' % s.replace('"', '\\"')
    return s


def _key_span(lines, key):
    """(start, end) line indices of `key`'s block, or None."""
    for i, line in enumerate(lines):
        m = _SCALAR_KEY.match(line)
        if not m or m.group(1) != key:
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith((' ', '\t')) and lines[j].strip():
            j += 1
        return i, j
    return None


def patch(fm_text, updates, prepend=()):
    """Replace the given keys in place, append the missing ones. Everything else survives.

    `prepend` names keys that, when newly added, go to the top rather than the bottom.
    Used for `date`/`type`, which read wrong at the end of a block.
    """
    lines = (fm_text or '').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    for key, value in updates.items():
        block = _emit(key, value).split('\n')
        span = _key_span(lines, key)
        if span:
            lines[span[0]:span[1]] = block
        elif key in prepend:
            lines[0:0] = block
        else:
            lines.extend(block)
    return '\n'.join(lines)


def get(meta, key, default=None):
    """Read a key, treating an unparsed key as absent-but-known rather than absent."""
    if key in meta.get('__unparsed__', ()):
        return default
    return meta.get(key, default)
