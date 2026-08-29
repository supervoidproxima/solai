# -*- coding: utf-8 -*-
"""START-HERE.md - the first three moves, written into the place itself.

The setup page can say what to do next, but the page is a tab that gets closed and the place
is not. D18 already demands that a stranger can orient in five minutes; this is that file for
the stranger who is the operator, ten minutes after pressing create.

Everything in it is derived: the loop comes from the manifest, the skills from the classes,
the folders from the declared folder list. Nothing here is per-type prose, because a paragraph
written once per archetype is a paragraph that drifts from the archetype.

It is generated and says so. The place's own orientation file, `_system/state.md`, is seeded
once and owned by the person - the two are deliberately different files.
"""
from . import table


def render(L, arch, classes, answers, inbox=''):
    name = answers.get('name') or 'this place'
    remit = (answers.get('remit') or '').strip()
    first_by = answers.get('first_artefact_by') or 'default'
    first = (answers.get('first_artefact') or '').strip()

    out = ['# Start here', '']
    if remit:
        out += [remit, '']
    out += ['A `%s` place, built by solai %s. **This file is generated** and is rewritten '
            'every time the place is re-planned. Your own notes belong in `_system/state.md`.'
            % (arch.name, answers.get('package_version', '')), '']

    # ------------------------------------------------------------------ opening a session
    out += ['## Open a session here', '',
            'The skills below exist only inside this folder. Open a terminal in the folder '
            'that contains this file and start Claude Code there:', '',
            '```', 'cd "%s"' % name, 'claude', '```', '']

    # ------------------------------------------------------------------ the inbox
    if inbox:
        out += ['## First, the inbox', '',
                '`%s/` holds what was handed in at setup. Read each one and file it: what '
                'constitutes this place, what informs it, what is a plan. The inbox is '
                'cleared, not archived - it is empty when the reading is done.' % inbox, '']

    # ------------------------------------------------------------------ session one
    steps = [s for s in arch.loop][:3]
    if steps:
        rows = [[str(s.get('n', i + 1)), s.get('name', ''),
                 '`%s`' % s.get('skill', '-'), '`%s`' % s.get('out', '')]
                for i, s in enumerate(steps)]
        out += ['## Session one', '',
                'The first three steps of the loop. The rest is in `CLAUDE.md`.', '',
                table(['#', 'What happens', 'Command', 'Writes to'], rows), '']

    # ------------------------------------------------------------------ the gate
    first_class = classes[0] if classes else None
    done = []
    if first_class:
        done.append('at least one `%s` card in `%s/`, and it names its source'
                    % (first_class.name, first_class.folder))
    if inbox:
        done.append('the inbox empty, or what is left in it explained in `_system/state.md`')
    done.append('`/solai check` reporting clean')
    out += ['## What finishing session one looks like', '',
            '\n'.join('- %s' % d for d in done), '']

    # ------------------------------------------------------------------ the open promise
    if first_by != 'operator':
        out += ['## Nobody has promised anything yet', '',
                'The first artefact reads *%s* - the type\'s own sentence, not yours. It is '
                'what lifted the empty-folder cap so this place could be built at all. Name '
                'the real one, with a date, and this place gets a denominator it did not '
                'write for itself.' % (first or 'unnamed'), '']

    # ------------------------------------------------------------------ where things are
    where = [['The rules this place runs by', '`CLAUDE.md`'],
             ['What a card must carry', '`_system/data-dictionary.md`'],
             ['Where things stand, in your words', '`_system/state.md`'],
             ['What built this, and under which rules', '`_system/os/vault.md`'],
             ['The counts, as a page', '`dashboard.html`']]
    out += ['## Where everything else is', '', table(['Question', 'File'], where)]
    return '\n'.join(out).rstrip('\n') + '\n'
