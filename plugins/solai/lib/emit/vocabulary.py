# -*- coding: utf-8 -*-
"""`_system/vocabulary.md`: the closed sets, and the rule for changing them.

Two vocabularies in one file, because they are governed identically and splitting them
produced two files nobody read:

    keys   every frontmatter key that may appear anywhere. GENERATED from the declarations
    tags   the thematic facets. SEEDED empty, because tags cannot be derived from anything

A closed set with no amendment procedure is a wish. The procedure is stated at the top and
enforced by an assertion: a value in use that is not on the list is a defect, and a value
added without a change record is a defect too.
"""
from . import code, table


def keys_region(classes, arch, L):
    rows = [
        [code('date'), 'every file', 'ISO date, unquoted'],
        [code('type'), 'every file', 'what kind of note this is'],
        [code('tags'), 'every file', 'closed list below. `[]` is normal'],
        [code('title'), 'notes', 'human-readable title, so the filename can stay a slug'],
        [code('aliases'), 'notes', 'other names this note answers to'],
    ]
    if classes:
        rows += [[code('id'), 'cards', 'matches the filename'],
                 [code('status'), 'cards', 'see the status matrix']]
    seen = {r[0] for r in rows}
    for c in classes:
        for f in c.fields:
            k = code(f.name)
            if k in seen:
                continue
            seen.add(k)
            rows.append([k, c.prefix, (f.meaning or '').split('.')[0]])
        for l in c.links:
            k = code(l.field)
            if k in seen:
                continue
            seen.add(k)
            rows.append([k, c.prefix, 'link to %s' % l.target])
    return table(['Key', 'Used by', 'Meaning'], rows)


def skeleton(L, keys_text, src='unstamped'):
    from .. import regions as R
    return '\n\n'.join([
        '# Vocabulary',
        ('Two closed sets. A value not on a list may not be used, and a value added without '
         'a change record is a defect. Amending a list means editing this file and writing '
         '`CHG-NNN` in the same run.'),
        '## Frontmatter keys',
        ('Generated from the class declarations. A key here that no declaration defines, or '
         'a key in use that is not here, is what the validator reports.'),
        R.render('keys', keys_text, src),
        '## Tags',
        ('Seeded empty on purpose. A tag vocabulary cannot be derived from anything: it is a '
         'claim about what this vault will need to slice by, and it is worth making slowly.'),
        ('Rules. Lowercase kebab-case. A tag is a thematic facet and never duplicates '
         '`type`, `status`, or any typed link field: those are already fields, and a tag '
         'that repeats one is a second copy of a fact with nothing comparing them. '
         '`tags: []` is correct and common. Aim for none to three.'),
        table(['Tag', 'What it marks'], [['', '']]),
        ('Add the first row when the third note wants the same tag. Not before: a vocabulary '
         'invented ahead of the content describes the content you imagined.'),
    ]) + '\n'
