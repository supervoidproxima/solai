# -*- coding: utf-8 -*-
"""The data dictionary: five generated regions, one hand-owned.

Reproduces the shape the source vault arrived at over 226 change records, because that
shape is right and because a vault built by this package should read like a vault someone
maintained:

    1  status matrix        every class, lifecycle order, terminal after a divider
    2  enumerated fields    grouped by field name ACROSS classes, so `severity` is one row
    3  derived fields       what is computed, and by what
    4  schemas by class     the six-column table plus the body skeleton
    5  links between classes  partitioned by kind
    6  known drift          HAND-OWNED. Records reality against the declaration, and so
                            cannot be derived from it

Section 6 is the honest one. A generated reference with no place to say "here is where we
have not caught up yet" quietly asserts that no such place exists.
"""
from . import cell, code, enum_list, table

REGIONS = ('status-matrix', 'enums', 'derived', 'schemas', 'link-rules')


def _req(f, L):
    return L('dd.yes') if f.required else L('dd.no')


def _values(f, L, partition=None):
    if f.source == 'partition':
        return enum_list(partition) if partition else '(set at setup)'
    if f.values:
        return enum_list(f.values)
    return ''


# --------------------------------------------------------------------------- regions

def status_matrix(classes, L):
    rows = []
    for c in classes:
        live = ' -> '.join('`%s`' % s for s in c.lifecycle)
        term = ' | '.join('`%s`' % s for s in c.terminal)
        values = ' | '.join(x for x in (live, term) if x)
        notes = '; '.join('%s: %s' % (k, v) for k, v in c.status_notes.items())
        rows.append([c.prefix, values, notes])
    return table([L('dd.s1-class'), L('dd.s1-values'), L('dd.s1-notes')], rows)


def enums(classes, L, partition=None):
    """Grouped by field name across classes: one `severity` row, not one per class."""
    by_field = {}
    for c in classes:
        for f in c.fields:
            if f.type != 'enum' or f.derived_by:
                continue
            key = (f.name, tuple(f.values), f.meaning)
            by_field.setdefault(key, []).append(c.prefix)
    rows = []
    for (name, values, meaning), prefixes in sorted(by_field.items()):
        rows.append([code(name), ' '.join(prefixes), enum_list(values), meaning])
    return table([L('dd.s2-field'), L('dd.s2-classes'), L('dd.s2-values'), L('dd.s2-meaning')],
                 rows)


def derived(classes, L):
    rows = []
    for c in classes:
        for f in c.fields:
            if not f.derived_by:
                continue
            rows.append([code(f.name), c.prefix, f.type, code(f.derived_by)])
    if not rows:
        return '%s' % L('dd.none')
    return table([L('dd.s2-field'), L('dd.s1-class'), L('dd.s3-type'), L('dd.s3-computed')], rows)


def schema_section(c, L, partition=None, prefixes=None):
    """One class: the heading, the six-column table, the body skeleton.

    `prefixes` maps class name to ID prefix. Without it a link to `proposal` renders as
    `[[PRO-NNN]]` instead of the declared `[[PRP-NNN]]`, which is a wrong example in the
    one document people copy examples out of.
    """
    prefixes = prefixes or {}
    head = '### %s (%s, %s)' % (c.prefix, code(c.folder + '/'), code('/' + c.skill))
    lines = [head]
    if c.purpose:
        lines.append(c.purpose)
    rows = []
    rows.append([code('id'), 'scalar', '1', L('dd.yes'), code(c.prefix + '-NNN'), ''])
    rows.append([code('type'), 'scalar', '1', L('dd.yes'), code(c.name), ''])
    rows.append([code('date'), 'date', '1', L('dd.yes'), 'YYYY-MM-DD', ''])
    rows.append([code('status'), 'enum', '1', L('dd.yes'),
                 enum_list(c.statuses), c.status_default and ('default: `%s`' % c.status_default) or ''])
    for f in c.fields:
        rows.append([code(f.name), f.type, f.card, _req(f, L), _values(f, L, partition),
                     f.meaning + (' Derived.' if f.derived_by else '')])
    for l in c.links:
        vals = '`[[%s-NNN]]`' % prefixes.get(l.target, l.target.upper()[:3])
        note = l.meaning
        if l.kind == 'bidirectional':
            note = (note + ' Reciprocal: `%s.%s`.' % (l.target, l.reciprocal)).strip()
        rows.append([code(l.field), 'list<wl>', l.card, L('dd.no'), vals, note])
    rows.append([code('tags'), 'list<str>', '0..N', L('dd.no'), '', ''])
    lines.append(table([L('dd.s4-field'), L('dd.s4-type'), L('dd.s4-card'), L('dd.s4-req'),
                        L('dd.s4-values'), L('dd.s4-meaning')], rows))
    if c.required_h2 or c.optional_h2:
        parts = []
        if c.required_h2:
            parts.append('%s: %s' % (L('dd.s4-required-h2'),
                                     ', '.join('`%s`' % h for h in c.required_h2)))
        if c.optional_h2:
            parts.append('%s: %s' % (L('dd.s4-optional-h2'),
                                     ', '.join('`%s`' % h for h in c.optional_h2)))
        lines.append('**%s.** %s.' % (L('dd.s4-body'), '. '.join(parts)))
    if c.status_rules.get('terminal_callout'):
        lines.append(L('dd.s4-terminal'))
    return '\n\n'.join(lines)


def schemas(classes, L, partition=None, prefixes=None):
    prefixes = prefixes or {c.name: c.prefix for c in classes}
    return '\n\n'.join(schema_section(c, L, partition, prefixes) for c in classes)


def link_rules(classes, L):
    bidir, oneway, lateral, lookup = [], [], [], []
    seen_pairs = set()
    for c in classes:
        for l in c.links:
            if l.kind == 'bidirectional':
                pair = tuple(sorted([(c.name, l.field), (l.target, l.reciprocal)]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                bidir.append('- `%s.%s[]` <-> `%s.%s[]`%s'
                             % (c.name, l.field, l.target, l.reciprocal,
                                (' - ' + l.meaning) if l.meaning else ''))
            elif l.kind == 'lateral':
                lateral.append('- `%s.%s[]` -> `%s`%s'
                               % (c.name, l.field, l.target,
                                  (' - ' + l.meaning) if l.meaning else ''))
            elif l.kind == 'lookup':
                lookup.append('- `%s.%s[]` -> `%s`' % (c.name, l.field, l.target))
            else:
                oneway.append('- `%s.%s[]` -> `%s`%s'
                              % (c.name, l.field, l.target,
                                 (' - ' + l.meaning) if l.meaning else ''))
    blocks = []
    for label, items in ((L('dd.s5-bidirectional'), bidir), (L('dd.s5-oneway'), oneway),
                         (L('dd.s5-lateral'), lateral), (L('dd.s5-lookup'), lookup)):
        if items:
            blocks.append('**%s.**\n%s' % (label, '\n'.join(items)))
    return '\n\n'.join(blocks)


def render_all(classes, L, partition=None, lookups=()):
    """-> {region_id: text}. The engine decides where they land; this decides what they say."""
    prefixes = {c.name: c.prefix for c in list(classes) + list(lookups)}
    return {
        'status-matrix': status_matrix(classes, L),
        'enums': enums(classes, L, partition),
        'derived': derived(classes, L),
        'schemas': schemas(classes, L, partition, prefixes),
        'link-rules': link_rules(classes, L),
    }


def skeleton(L, regions_text, region_order=REGIONS, src='unstamped'):
    """The whole file body, markers included, for a first write."""
    from .. import regions as R
    heads = {
        'status-matrix': L('dd.s1'),
        'enums': L('dd.s2'),
        'derived': L('dd.s3'),
        'schemas': L('dd.s4'),
        'link-rules': L('dd.s5'),
    }
    out = ['# %s' % L('dd.title'), L('dd.generated-note')]
    for rid in region_order:
        out.append('## %s' % heads[rid])
        out.append(R.render(rid, regions_text[rid], src))
    out.append('## %s' % L('dd.s6'))
    out.append(L('dd.s6-hint'))
    return '\n\n'.join(out) + '\n'
