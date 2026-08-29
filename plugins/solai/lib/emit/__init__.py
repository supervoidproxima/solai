# -*- coding: utf-8 -*-
"""Emitters: declarations in, Markdown out.

An emitter knows nothing about the filesystem. It takes declarations and returns text,
so it can be tested by comparing strings and can never half-write a vault. The engine
owns every byte that lands on disk.
"""
import os
import tomllib


class Labels(object):
    """Interface strings for one output language.

    Headings are never hardcoded in an emitter. A vault that answered "Russian" at setup
    and then received an English data dictionary would have been asked a decorative
    question, and the point of asking was that it is not decorative.
    """

    def __init__(self, data):
        self.data = data

    def __call__(self, path, default=None):
        section, _, key = path.partition('.')
        val = self.data.get(section, {})
        val = val.get(key) if isinstance(val, dict) else None
        if val is None:
            if default is not None:
                return default
            raise KeyError('no label %r for language %r' % (path, self.data.get('language')))
        return val

    @property
    def language(self):
        return self.data.get('language', 'en')


def load_labels(pkg_root, language):
    p = os.path.join(pkg_root, 'common', 'labels', '%s.toml' % language)
    if not os.path.exists(p):
        p = os.path.join(pkg_root, 'common', 'labels', 'en.toml')
    with open(p, 'rb') as fh:
        return Labels(tomllib.load(fh))


# --------------------------------------------------------------------------- helpers

def cell(value):
    """Escape a value for a markdown table cell.

    A pipe inside a wikilink alias must be escaped or it splits the row. Obsidian renders
    the escaped form correctly, so this is the convention rather than a workaround.
    """
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        value = ', '.join(str(v) for v in value)
    s = str(value).replace('\n', ' ').strip()
    return s.replace('|', '\\|')


def table(headers, rows, align=None):
    """Markdown table. Empty rows yield an empty string, never a headerless skeleton."""
    if not rows:
        return ''
    head = '| ' + ' | '.join(cell(h) for h in headers) + ' |'
    if align:
        sep = '| ' + ' | '.join(align) + ' |'
    else:
        sep = '| ' + ' | '.join('---' for _ in headers) + ' |'
    body = '\n'.join('| ' + ' | '.join(cell(c) for c in r) + ' |' for r in rows)
    return '\n'.join([head, sep, body])


def code(s):
    return '`%s`' % s


def enum_list(values):
    """Raw pipes. `cell()` escapes them exactly once on the way into a table; escaping
    here as well produced `\\\\|` in the first draft."""
    return ' | '.join('`%s`' % v for v in values)
