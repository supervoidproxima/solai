# -*- coding: utf-8 -*-
"""`_system/os/vault.md`: the bond between a vault and the package that built it.

Everything that makes a re-run, an upgrade or an audit possible lives here: which version
built this, at which tier, in which language, what the vault promised to produce, which
doctrine principles it waived and why, which assertions it suppressed and when.

Three deliberate properties:

  - It is declared OUT OF SCOPE of the vault's own governance. It is engine state, not vault
    content. That is also the cut that lets it exist before the registry that would
    otherwise have to govern it.
  - `first-artefact` is not decoration. It is the denominator of every ratio reported.
  - Waivers and suppressions never expire and never disappear from `status`. A vault may
    refuse a rule; it may not make the refusal invisible.
"""
from . import code, table


def render(answers, arch, classes, tier, counts, package_version, waivers=(), suppressed=()):
    a = answers
    lines = [
        '# Vault bond',
        '',
        'Written and maintained by the `solai` package. This file is engine state: it is out '
        'of scope of the vault\'s own conventions, and it is the one file to read when asking '
        'what built this vault and under which rules.',
        '',
        '## Identity',
        '',
        table(['Key', 'Value'], [
            ['name', a.get('name', '')],
            ['archetype', code(arch.name)],
            ['tier', code(tier)],
            ['output language', a.get('output_language_name', a.get('output_language', 'en'))],
            ['package version', code(package_version)],
            ['created', a.get('today', '')],
            ['remit', a.get('remit', 'Unknown')],
        ]),
        '',
        '## The promise',
        '',
        '**First artefact: %s**%s' % (
            a.get('first_artefact') or 'NOT NAMED',
            '' if a.get('first_artefact_by') == 'operator'
            else '  (the type\'s default. Nobody has promised this yet.)'),
        '',
        ('Every ratio this package reports is measured against that. It is not a target to '
         'be moved when the number looks bad: moving it is the failure the ratio exists to '
         'detect.'),
        '',
        '## Counts at build',
        '',
        table(['What', 'Count'], [
            ['content files', counts.get('content', 0)],
            ['system files written by the package', counts.get('system', 0)],
            ['skills written by the package', counts.get('skills', 0)],
            ['card classes', len(classes)],
        ]),
        '',
        ('Bootstrap ratio %d system to %d content. This package declares '
         '`induces: authoring-instead-of-shipping`, and its own output counts on the system '
         'side of the ratio it reports. It may not be argued out of that column.'
         % (counts.get('system', 0), counts.get('content', 0))),
        '',
        '## Classes',
        '',
        table(['Class', 'Prefix', 'Folder', 'Command'],
              [[c.name, c.prefix, code(c.folder + '/'), code('/' + c.skill)] for c in classes])
        or '(none)',
        '',
        '## Waived principles',
        '',
        (table(['Principle', 'Reason', 'Date', 'Change'],
               [[w.get('id'), w.get('reason'), w.get('date'), w.get('change')] for w in waivers])
         if waivers else
         'None. A waiver names a doctrine ID, a reason, a date and a change record, and is '
         'reported here for as long as it stands.'),
        '',
        '## Suppressed assertions',
        '',
        (table(['Assertion', 'Reason', 'Date'],
               [[s.get('id'), s.get('reason'), s.get('date')] for s in suppressed])
         if suppressed else
         'None. An assertion may be suppressed with a reason and a date. It may never be '
         'edited, and a suppression never stops being reported.'),
        '',
        '## Provenance',
        '',
        ('Per-file state is written below by the engine on each apply: `pristine` means it '
         'still matches what the package shipped, `local-edited` means it diverged, '
         '`local-decision` means it diverged deliberately and names the change record. An '
         'upgrade applies over pristine files, proposes a patch for edited ones, and never '
         'touches a local decision.'),
    ]
    return '\n'.join(lines) + '\n'


def frontmatter(answers, arch, tier, package_version):
    return '\n'.join([
        'date: %s' % answers.get('today', ''),
        'type: reference',
        'title: "Vault bond (GENERATED)"',
        'solai-package: %s' % package_version,
        'solai-archetype: %s' % arch.name,
        'solai-tier: %s' % tier,
        'output-language: %s' % answers.get('output_language', 'en'),
        'first-artefact: "%s"' % (answers.get('first_artefact') or ''),
        'first-artefact-by: %s' % (answers.get('first_artefact_by') or 'default'),
        'tags: []',
    ])
