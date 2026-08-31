# -*- coding: utf-8 -*-
"""A class declaration into a working `/gap`-style skill, in the vault's own `.claude/skills/`.

Five regions are generated and belong to the engine. The rest of the file is seeded once
and belongs to the user, because the parts that cannot be derived are exactly the parts
worth writing by hand: how to tell a `high` from a `medium`, what this class is not, the
example that settles an argument.

  generated: frontmatter, step-id, step-fields, step-body, step-write
  seeded:    the rubrics, SELF-EVAL, AUTO-IMPROVE, RULES

The size gate runs before the write, not after. A skill over 200 lines is refused with the
name of the region to move out, because "keep it under 200" enforced by nobody is how the
one 234-line skill in the existing set got there.
"""
from . import cell, code, enum_list, table

REGIONS = ('frontmatter', 'step-id', 'step-fields', 'step-body', 'step-write')
LINE_CAP = 200


# --------------------------------------------------------------------------- regions

def frontmatter(c, L, vault_name, tier, output_language):
    trig = ['"/%s"' % c.skill] + ['"%s"' % t for t in c.skill_triggers]
    desc = c.purpose.rstrip('.')
    if c.field('kind') and c.field('kind').values:
        desc += '. Required kind: %s' % ', '.join(c.field('kind').values)
    lines = [
        'name: %s' % c.skill,
        # quoted: a purpose containing ": " is not a valid bare YAML scalar
        'description: "%s. Writes %s/%s-NNN.md in the %s vault."'
        % (desc.replace('"', "'"), c.folder, c.prefix, vault_name),
        'scope: local',
        'trigger_phrases:',
    ]
    lines += ['  - %s' % t for t in trig]
    lines += [
        'permissions:',
        '  read: true',
        '  write: true',
        '  execute: false',
        '  network: false',
    ]
    if tier in ('standard', 'governed'):
        lines += [
            'vault_contract:',
            '  contract_version: 1',
            '  reads:',
            '    - "%s/"' % c.folder,
            '    - "_system/data-dictionary.md"',
            '  writes:',
            '    - "%s/"' % c.folder,
            '  generates: []',
            '  cadence: "on-demand, whenever a %s is stated"' % c.name,
            '  mints: %s-NNN' % c.prefix,
            '  induces: %s' % c.induces,
        ]
    return '\n'.join(lines)


def step_id(c, L):
    return '\n'.join([
        'Glob `%s/%s-*.md`. Take the highest NNN and add one. With none present, start at '
        '`%s-001`.' % (c.folder, c.prefix, c.prefix),
        '',
        'Zero-padded to three digits. Numbers are never reused, and never renumbered: a '
        'gap in the sequence is cheaper than a reference that silently points somewhere new.',
    ])


def step_fields(c, L, partition=None):
    rows = [[code('id'), L('skill.frontmatter'), L('dd.yes'), '`%s-NNN`, matching the filename' % c.prefix],
            [code('type'), L('skill.frontmatter'), L('dd.yes'), code(c.name)],
            [code('date'), L('skill.frontmatter'), L('dd.yes'), 'today, `YYYY-MM-DD`'],
            [code('status'), L('skill.frontmatter'), L('dd.yes'),
             '%s. New card: `%s`' % (enum_list(c.statuses), c.status_default)]]
    for f in c.fields:
        if f.derived_by:
            rows.append([code(f.name), L('skill.frontmatter'), L('dd.no'),
                         'DERIVED. Never type it: `%s` computes it' % f.derived_by])
            continue
        vals = enum_list(f.values) if f.values else (
            enum_list(partition) if (f.source == 'partition' and partition) else '')
        note = f.meaning
        if f.no_default:
            note = (note + ' No default: name the trigger or do not assign it.').strip()
        detail = '. '.join(x for x in (vals, note.rstrip('.')) if x)
        rows.append([code(f.name), L('skill.frontmatter'),
                     L('dd.yes') if f.required else L('dd.no'), detail + ('.' if detail else '')])
    for l in c.links:
        rows.append([code(l.field), L('skill.frontmatter'), L('dd.no'),
                     'wikilinks to %s. `[]` when none' % l.target])
    rows.append([code('tags'), L('skill.frontmatter'), L('dd.no'),
                 'from the closed list in `_system/vocabulary.md`. `[]` is correct and common'])
    out = [table([L('dd.s4-field'), L('skill.where'), L('dd.s4-req'), L('dd.s4-values')], rows)]
    recip = [l for l in c.links if l.kind == 'bidirectional']
    if recip:
        out.append('')
        out.append('**Reciprocal links.** ' + ' '.join(
            'Setting `%s` obliges the matching `%s.%s` entry on the target card, in the same run.'
            % (l.field, l.target, l.reciprocal) for l in recip))
    if any(f.derived_by for f in c.fields):
        out.append('')
        out.append('**Derived fields are not asked for.** Leave them out; the deriving script '
                   'owns them, and a hand-set value is a defect the validator reports.')
    return '\n'.join(out)


def step_body(c, L):
    if not c.required_h2 and not c.optional_h2:
        return ('No heading skeleton for this class: a quotation and a sentence of context. '
                'Imposing headings on it produces headings, not content.'
                + (('\n\nCitations: %s, collected under `%s`.' % (c.cite_style, c.sources_h3))
                   if c.cite_style == 'footnotes' else ''))
    lines = ['Write these headings, in this order:', '']
    for h in c.required_h2:
        lines.append('- `%s`' % h)
    if c.optional_h2:
        lines.append('')
        lines.append('Optional, after the required ones and in this order:')
        lines.append('')
        for h in c.optional_h2:
            lines.append('- `%s`' % h)
    lines += ['',
              'A required heading with nothing to say carries the single word `Unknown`. The '
              'heading is never dropped: an absent heading reads as "not applicable", and '
              'absence is a value, not silence.',
              '',
              '**This applies to body headings only, never to a frontmatter field.** An '
              'enumerated field takes one of its declared values or the card fails `CL-5`; '
              'an optional field with nothing to put in it is left **empty**, which already '
              'says "not stated" and says it in a form the validator can read.']
    if c.cite_style == 'footnotes':
        lines += ['',
                  'Citations are markdown footnotes: `[^N]` at the claim, and `[^N]: [[file#^anchor]]` '
                  'collected under `%s` at the end. A claim with no citation is an assumption, '
                  'and assumptions do not belong in this class.' % c.sources_h3]
    return '\n'.join(lines)


def step_write(c, L):
    lines = [
        'Write `%s/{ID}.md`. The filename is the bare ID: no slug, no date, no title.' % c.folder,
        '',
        'Report as:',
        '',
        '```',
        'v %s/{ID}.md' % c.folder,
        '  {one-line summary}',
        '  status {status}  links {n}',
        '```',
    ]
    if c.status_rules.get('terminal_callout'):
        lines += ['',
                  'A card written or moved to a terminal status (%s) opens its body with a '
                  'callout naming the reason and the date. Changing the status without the '
                  'callout leaves the prose asserting what the frontmatter denies.'
                  % ', '.join('`%s`' % s for s in c.terminal)]
    if c.archive_folder:
        lines += ['', 'Archived cards move to `%s/`.' % c.archive_folder]
    return '\n'.join(lines)


# --------------------------------------------------------------------------- seeded

def _rubric(c, field_name, L):
    f = c.field(field_name)
    if not f or not f.values:
        return None
    rows = [[code(v), f.value_notes.get(v, '')] for v in f.values]
    return '### How to choose `%s`\n\n%s\n\n%s' % (
        field_name, table([field_name, 'When'], rows),
        'Written by the engine from the declaration, then owned by you. Sharpen it against '
        'real cards: this is the part of the skill that cannot be derived.')


def seeded_body(c, L):
    """Everything the engine writes once and never touches again."""
    parts = []
    for r in c.skill_rubrics:
        block = _rubric(c, r, L)
        if block:
            parts.append(block)
    parts.append('## SELF-EVAL\n\n'
                 'Score the card just written: every required field present, every enum value '
                 'declared, every required heading present or carrying `Unknown`, every '
                 'reciprocal link written on both sides. Report the score and name the failures.')
    parts.append('## AUTO-IMPROVE\n\n'
                 'Below full marks, propose the smallest edit to this skill that would have '
                 'passed, and apply it only on confirmation. Check `CHANGELOG.md` first: a fix '
                 'already tried and reverted may not be re-proposed without new evidence.')
    rules = [
        '- One card, one object. If it needs "and", it is two cards.',
        '- Never invent a value for a required field. Ask, or write `Unknown`.',
        '- Status is read before the card is used anywhere, and reviewed whenever the card changes.',
        '- Field schemas live in `_system/data-dictionary.md`. This file does not restate them.',
        '- SKILL.md stays under %d lines. Overflow goes to a sibling file.' % LINE_CAP,
    ]
    if c.induces and c.induces != 'none':
        rules.append('- This skill declares `induces: %s`. Watch for it in your own output.'
                     % c.induces)
    parts.append('## RULES\n\n' + '\n'.join(rules))
    return '\n\n'.join(parts)


# --------------------------------------------------------------------------- assembly

def render_regions(c, L, vault_name, tier, output_language, partition=None):
    return {
        'frontmatter': frontmatter(c, L, vault_name, tier, output_language),
        'step-id': step_id(c, L),
        'step-fields': step_fields(c, L, partition),
        'step-body': step_body(c, L),
        'step-write': step_write(c, L),
    }


def skeleton(c, L, regions_text, shared_paths=(), src='unstamped'):
    """Full first-write body with markers. The frontmatter region sits inside the YAML block,
    which is legal: a `#`-prefixed marker is a YAML comment."""
    from .. import regions as R
    steps = [('step-id', L('skill.step-id')),
             ('step-fields', L('skill.step-fields')),
             ('step-body', L('skill.step-body')),
             ('step-write', L('skill.step-write'))]
    out = ['---',
           R.render('frontmatter', regions_text['frontmatter'], src, comment='# '),
           '---',
           '',
           '=== %s ===' % c.title.upper(),
           '',
           'ARGUMENTS: $ARGUMENTS',
           'A stated %s, or a source to sweep for them.' % c.name,
           '']
    if shared_paths:
        out += ['Read first, once per run:', '']
        out += ['- `%s`' % p for p in shared_paths]
        out += ['']
    for n, (rid, title) in enumerate(steps, 1):
        out += ['## STEP %d - %s' % (n, title), '',
                R.render(rid, regions_text[rid], src), '']
    out += [seeded_body(c, L), '']
    return '\n'.join(out)


def check_size(text, c):
    """-> (ok, lines, advice). Refuse before writing, and name what to move."""
    n = len(text.split('\n'))
    if n <= LINE_CAP:
        return True, n, ''
    biggest = 'the rubric sections' if c.skill_rubrics else 'the field table'
    return False, n, ('%s/SKILL.md would be %d lines, over the %d cap. Move %s to '
                      '`.claude/skills/%s/rubrics.md` and reference it by path.'
                      % (c.skill, n, LINE_CAP, biggest, c.skill))
