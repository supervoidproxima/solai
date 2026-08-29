# -*- coding: utf-8 -*-
"""The Obsidian Base: one view per card class, generated from each class's `[view]` block.

Two rules, both learned from a real vault:

  - Never emit `columnSize` or `viewport`. Obsidian writes those itself the moment a human
    opens the file, and hashing them would mark the most visible artefact in the vault as
    hand-edited on the second run. They are also stripped before hashing (see VOLATILE).
  - A `sort:` on a property no declaration defines is dead weight. NIS's CATALOGUE.base
    carries eight of them, left behind by a field rename. Sorting here can only reference
    declared fields, because `decl` rejects a view column that is not one.
"""

VOLATILE = [r'^\s*columnSize:', r'^\s*viewport:']


def _q(value):
    return value if str(value).replace('.', '').replace('_', '').isalnum() else '"%s"' % value


def view(c):
    name = c.name if c.name.endswith('s') else c.name + 's'
    lines = ['  - type: table',
             '    name: %s' % name,
             '    filters:',
             '      and:',
             '        - type == "%s"' % c.name]
    cols = c.view_columns or ['file.name', 'status', 'tags']
    lines.append('    order: [%s]' % ', '.join(cols))
    if c.view_sort:
        lines.append('    sort:')
        for s in c.view_sort:
            lines.append('      - property: %s' % s.get('property'))
            lines.append('        direction: %s' % s.get('direction', 'ASC'))
    return '\n'.join(lines)


def render(classes, lookups=()):
    """The whole `.base` file. Obsidian owns the layout keys; this owns the data keys."""
    out = ['properties:', '  note.text:', '    displayName: description', 'views:']
    for c in list(classes) + list(lookups):
        out.append(view(c))
    return '\n'.join(out) + '\n'
