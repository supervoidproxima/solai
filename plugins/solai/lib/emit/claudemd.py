# -*- coding: utf-8 -*-
"""The vault's CLAUDE.md: seeded prose the user owns, generated tables the engine owns.

The division is the whole design. NIS's CLAUDE.md is 102 KB, and roughly 90 KB of it
restates field schemas that also live in its data dictionary, kept in step by discipline
alone. So here:

    CLAUDE.md   answers WHERE a thing goes and WHICH command makes it
    dictionary  answers WHAT SHAPE it is

The card-index region carries five columns and never names a field. An assertion greps for
declared field names appearing outside it, so the duplication cannot creep back.
"""
import io
import os

from . import code, table

GENERATED = ('language', 'id-standard', 'card-index', 'loop', 'structure',
             'frontmatter', 'naming', 'citation')
SEEDED = {
    'header': 'claude/00-header.md',
    'purpose': 'claude/10-purpose.md',
    'constraints': 'claude/20-constraints.md',
    'handoff': 'claude/85-handoff.md',
    'change-discipline': 'claude/95-change-discipline.md',
    'honesty': 'claude/99-honesty.md',
}
HEADINGS = {
    'language': None, 'id-standard': None, 'card-index': None, 'loop': None,
    'structure': None, 'frontmatter': None, 'naming': None, 'citation': None,
}

LANGUAGE_NAMES = {'en': 'English', 'ru': 'Russian', 'kk': 'Kazakh'}


def language_list(answers, key, fallback=('en',)):
    """-> list of codes. One answer arrives as a string and several arrive as a list, because
    that is how the engine's own `key=a|b` parsing hands them over."""
    got = answers.get(key) or list(fallback)
    if isinstance(got, str):
        got = [p.strip() for p in got.replace('|', ',').split(',') if p.strip()]
    return [c for c in got if c] or list(fallback)


def language_names(codes):
    return [LANGUAGE_NAMES.get(c, c) for c in codes]


def human_list(names):
    """a, b and c. Written once because it is read in two regions, and a list joined two
    different ways in one file reads as two different rules."""
    if len(names) < 2:
        return names[0] if names else ''
    return '%s and %s' % (', '.join(names[:-1]), names[-1])


def fragment(pkg_root, rel, answers):
    p = os.path.join(pkg_root, 'common', 'fragments', rel.replace('/', os.sep))
    with io.open(p, encoding='utf-8') as fh:
        text = fh.read()
    for k, v in answers.items():
        text = text.replace('{%s}' % k, str(v))
    return text.rstrip('\n')


# --------------------------------------------------------------------------- generated

def language(L, answers):
    content = language_names(language_list(answers, 'content_languages',
                                           (answers.get('output_language') or 'en',)))
    written = human_list(content)
    lines = [
        '## Language',
        '',
        'Reasoning, internal logic and headings in this file: British English.',
        '',
        'Everything the vault produces for a reader, cards, analyses, deliverables and '
        'commit messages: **%s**.' % answers.get('output_language_name', 'English'),
        '',
        'Content may be written in: **%s**. A card is written in one of them, whole: the '
        'language may change between cards and never inside one.' % written,
        '',
        'Codes stay as they are in any language: identifiers, standard abbreviations, '
        'system names, and anything quoted verbatim from a source.',
    ]
    return '\n'.join(lines)


def card_naming_rows(classes):
    """How cards are named, one row per policy in use.

    Derived rather than asserted. A vault may be mixed - one class named by slug because a
    graph view of sixteen nodes reading DTY-001 to DTY-016 is useless for the one thing that
    view is for, and another kept on bare identifiers - so a single hardcoded row is wrong
    for that vault and cannot be corrected from inside it.
    """
    if not classes:
        return []
    bare = [c for c in classes if getattr(c, 'filename', 'bare-id') != 'slug']
    slug = [c for c in classes if getattr(c, 'filename', 'bare-id') == 'slug']
    rows = []
    if bare:
        label = 'Card' if not slug else 'Card (%s)' % ', '.join(c.name for c in bare)
        rows.append([label, 'bare ID', '`%s-001.md`' % bare[0].prefix])
    if slug:
        label = 'Card' if not bare else 'Card (%s)' % ', '.join(c.name for c in slug)
        rows.append([label,
                     '`slug.md`, named for the thing. The identifier lives in `id` and is '
                     'repeated in `aliases`',
                     '`a-name-for-the-thing.md`'])
    return rows


def naming(L, answers, classes=()):
    policy = (answers.get('filename_language') or 'english').strip()
    content = language_names(language_list(answers, 'content_languages',
                                           (answers.get('output_language') or 'en',)))
    rows = [['Dated note', '`YYYY-MM-DD-slug.md`', '`2026-08-27-budget-cycle-review.md`'],
            ['Undated note', '`slug.md`', '`budget-cycle-review.md`'],
            ]
    rows += card_naming_rows(classes)
    rows += [
            ['Folder', '`slug/`', '`registry/`, `_system/`'],
            ['Frontmatter key', '`kebab-case`', '`demand-voices`'],
            ['Tag', '`kebab-case`', '`budget-cycle`']]
    out = ['## Naming', '',
           'Kebab-case: lowercase, single hyphens, no spaces, no underscores, no capitals.',
           '', table(['Kind', 'Form', 'Example'], rows), '']
    if policy == 'content':
        out += ['**What a name names decides its language, not who wrote it.** Structure is '
                'named in English: folders, identifiers, system paths, frontmatter keys and '
                'tags, all ASCII kebab. A file named for its subject may be named in %s, and '
                'may use spaces where that reads better.' % human_list(content),
                '',
                'The two rules do not overlap. If a name would sit in both columns - a folder '
                'named for its subject - it is structure, and it is English.',
                '']
    else:
        out += ['File names are ASCII kebab whatever language the content is in. A title in '
                'another language lives in frontmatter `title:` and `aliases:`, which is '
                'what wikilinks and search read anyway.',
                '']
    out += ['The date prefix uses the same hyphen as the rest, so the whole filename is one '
            'kebab string and the date is always the first ten characters. Human-readable '
            'titles live in frontmatter `title:` and `aliases:`, so renaming a document '
            'never breaks a wikilink.']
    return '\n'.join(out)


def id_standard(L, classes, arch, answers):
    rows = []
    for c in classes:
        rows.append([c.title, code(c.prefix + '-NNN'), code(c.minted_by)])
    rows.append(['Change record', code('CHG-NNN'), code('skill:place')])
    return '\n'.join([
        '## %s' % L('claude.id-standard'),
        '',
        'Three uppercase letters, a hyphen, three digits. The number is never reused and '
        'never renumbered: a hole in a sequence costs less than a reference that silently '
        'points somewhere new.',
        '',
        table([L('claude.i-class'), L('claude.i-format'), L('claude.i-minted')], rows),
    ])


def card_index(L, classes):
    """Routing only. Naming a field here is the defect assertion DR-1 exists to catch."""
    rows = [[c.title, code(c.prefix + '-NNN'), code(c.folder + '/'), code('/' + c.skill),
             c.purpose] for c in classes]
    if not rows:
        return '## %s\n\nThis vault has no card classes. Add one with `/solai class <name>`.' \
               % L('claude.card-index')
    return '\n'.join([
        '## %s' % L('claude.card-index'),
        '',
        L('claude.card-index-hint'),
        '',
        table([L('claude.c-class'), L('claude.c-id'), L('claude.c-folder'),
               L('claude.c-skill'), L('claude.c-purpose')], rows),
        '',
        'Full field schemas: `_system/data-dictionary.md`.',
    ])


def loop(L, arch):
    if not arch.loop:
        return ''
    rows = [[p.get('n'), p.get('name'), code(p.get('skill', '-')), code(p.get('out', ''))]
            for p in arch.loop]
    return '\n'.join([
        '## %s' % L('claude.loop'),
        '',
        table([L('claude.p-step'), L('claude.p-name'), L('claude.p-skill'),
               L('claude.p-out')], rows),
    ])


def structure(L, arch, extra=()):
    rows = [[code(f.get('path') + '/'), f.get('purpose', '')] for f in arch.folders]
    rows += [[code(p), d] for p, d in extra]
    return '\n'.join([
        '## %s' % L('claude.structure'),
        '',
        table([L('claude.st-folder'), L('claude.st-holds')], rows),
    ])


def frontmatter(L, arch, classes):
    date_fmt = arch.ids.get('date', 'YYYY-MM-DD')
    rows = [
        [code('date'), date_fmt, L('dd.yes'), 'unquoted ISO'],
        [code('type'), 'text', L('dd.yes'),
         ', '.join(code(c.name) for c in classes) if classes else code('note')],
        [code('tags'), 'list', L('dd.no'), 'closed list in `_system/vocabulary.md`. `[]` is normal'],
    ]
    if classes:
        slug = [c for c in classes if getattr(c, 'filename', 'bare-id') == 'slug']
        rows.insert(2, [code('id'), 'text', 'cards',
                        'matches the filename' if not slug else
                        'the identifier. It matches the filename except on %s, which '
                        'is named by slug' % ', '.join(code(c.name) for c in slug)])
        rows.insert(3, [code('status'), 'enum', 'cards', 'see the status matrix'])
    return '\n'.join([
        '## %s' % L('claude.frontmatter'),
        '',
        table([L('claude.fm-key'), L('claude.fm-format'), L('claude.fm-required'),
               L('claude.fm-values')], rows),
        '',
        'Keys are kebab-case and come from the closed vocabulary. A new key is an amendment '
        'to `_system/vocabulary.md` plus a change record. List fields are written as `[]` '
        'rather than omitted, so an empty value is distinguishable from an unset one.',
    ])


def citation(L, classes):
    styles = {c.cite_style for c in classes if c.cite_style != 'none'}
    if not styles:
        return ('## Sources\n\n'
                'A claim that drives a decision names its source inline as a wikilink. A fact '
                'without a source is an assumption.')
    if 'footnotes' in styles:
        return '\n'.join([
            '## Citations',
            '',
            'Markdown footnotes. `[^N]` at the claim, `[^N]: [[file#^anchor]]` collected at '
            'the end of the file under the class\'s sources heading.',
            '',
            '- Numbering is per file and append-only. A new citation takes `max + 1`; numbers '
            'are never resorted when one is inserted above.',
            '- The same target cited twice reuses its number, and the definition is written once.',
            '- Frontmatter never carries a footnote. Wikilinks there are bare and quoted.',
        ])
    return '## Citations\n\nInline wikilinks at the claim.'


# --------------------------------------------------------------------------- assembly

def render_generated(L, arch, classes, answers, extra_folders=()):
    out = {
        'language': language(L, answers),
        'id-standard': id_standard(L, classes, arch, answers),
        'card-index': card_index(L, classes),
        'loop': loop(L, arch),
        'structure': structure(L, arch, extra_folders),
        'frontmatter': frontmatter(L, arch, classes),
        'naming': naming(L, answers, classes),
        'citation': citation(L, classes),
    }
    return {k: v for k, v in out.items() if v}


def skeleton(pkg_root, L, arch, classes, answers, region_order, generated_text,
             src='unstamped'):
    """First write: seeded fragments as plain prose, generated regions inside markers."""
    from .. import regions as R
    parts = []
    for rid in region_order:
        if rid in generated_text:
            parts.append(R.render(rid, generated_text[rid], src))
        elif rid in SEEDED:
            parts.append(fragment(pkg_root, SEEDED[rid], answers))
    return '\n\n'.join(parts) + '\n'
