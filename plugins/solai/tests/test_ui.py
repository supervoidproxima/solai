# -*- coding: utf-8 -*-
"""26 assertions on the setup surface: what it asks, what it offers, what it forwards,
and the plan gate.

The surface is the one part of the package a person drives with a mouse, and a mouse cannot
be told to plan first. So the rule that was prose in `interview.md` - show the plan, then
apply - is a token here, and most of these assertions are about that token: it must survive
an unchanged answer set and it must not survive a changed one. `UI-11` is the one people
find surprising: the token is SPENT by the apply that uses it, so a second identical create
has to be planned again. An apply that failed halfway leaves a disk the first plan no longer
describes, which is exactly when a stale approval does damage.

`UI-05` guards the other half. The page shows `mode` and `classes` as statements rather than
controls, and a statement that quietly reached the command line would be a control nobody
could see, and `UI-24` guards the types: this surface offers `role` today, and the ones it
does not offer are shown disabled with the reason rather than dropped from the page.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, 'skills', 'solai-scaffold'))

from lib import decl                                                # noqa: E402
import serve as UI                                                  # noqa: E402

EXPECTED = 44
NAME = 'ui'

ANS = {'name': 'T', 'remit': 'A fixture remit', 'output_language': 'en'}


def group_declarations(s):
    got = UI.archetypes(PKG)
    on_disk = sorted(d for d in os.listdir(os.path.join(PKG, 'archetypes'))
                     if os.path.isdir(os.path.join(PKG, 'archetypes', d)))
    s.eq('UI-01', 'every archetype on disk reaches the page', sorted(a['name'] for a in got),
         on_disk)

    role = [a for a in got if a['name'] == 'role'][0]
    s.eq('UI-02', 'the questions are the manifest\'s, not a list kept in the surface',
         role['asks'], list(decl.load_archetype(PKG, 'role').asks))

    s.eq('UI-37', "the type's opening line reaches the page, which prefills Purpose",
         role['defaults'].get('remit'),
         decl.load_archetype(PKG, 'role').defaults.get('remit'))

    s.eq('UI-36', 'the partition carries the field it binds to, which is what labels the input',
         role['partition'].get('binds'),
         decl.load_archetype(PKG, 'role').partition.get('binds'))

    project = [a for a in got if a['name'] == 'project'][0]
    s.ok('UI-03', 'what an archetype ships is carried to the page',
         project['classes'] and project['agents'] and project['workflows'],
         'project declares classes, agents and workflows; the page renders their counts')

    s.eq('UI-04', 'the answers with no control behind them are named',
         sorted(UI.INERT), ['classes', 'mode', 'output_language', 'partition'])

    s.eq('UI-05', 'an inert answer never reaches the engine',
         UI.engine_answers(dict(ANS, mode='greenfield', classes='a,b')),
         {k: v for k, v in ANS.items() if k not in UI.INERT})

    live = [a for a in got if a.get('active')]
    s.eq('UI-24', 'the surface offers exactly the types it declares active',
         sorted(a['name'] for a in live), sorted(UI.ACTIVE))
    dead = [a for a in got if not a.get('active') and not a.get('broken')]
    s.ok('UI-25', 'a kind not offered is still listed, with the reason',
         dead and all(a['deactivated'] for a in dead),
         'hiding it would understate what the package builds')


def group_gate(s):
    t = UI.answer_token('C:/x', 'role', ANS)
    s.eq('UI-06', 'the same answers fingerprint the same', UI.answer_token('C:/x', 'role', ANS), t)
    s.ok('UI-07', 'a changed answer changes the fingerprint',
         UI.answer_token('C:/x', 'role', dict(ANS, remit='Different')) != t)
    s.ok('UI-08', 'a changed archetype changes the fingerprint',
         UI.answer_token('C:/x', 'minimal', ANS) != t)
    s.eq('UI-09', 'an empty answer is not an answer',
         UI.answer_token('C:/x', 'role', dict(ANS, partition='')), t)

    gate = UI.PlanGate()
    s.ok('UI-10', 'create is refused for an answer set no plan was shown for',
         not gate.allows(t))
    gate.remember(t)
    used = gate.allows(t)
    gate.forget(t)
    s.ok('UI-11', 'the token is spent by the create that uses it',
         used and not gate.allows(t),
         'a second create has to be planned again: the first may have failed halfway')


def group_argv(s):
    plain = UI.engine_argv('C:/x', 'role', ANS)
    s.ok('UI-12', 'planning never carries --apply', '--apply' not in plain)
    s.ok('UI-13', 'creating carries --apply',
         '--apply' in UI.engine_argv('C:/x', 'role', ANS, apply_it=True))
    argv = UI.engine_argv('C:/x', 'role', dict(ANS, partition=''))
    s.ok('UI-14', 'an empty answer is not put on the command line',
         not any(a.startswith('partition=') for a in argv))
    s.ok('UI-26', 'every active kind is a real archetype on disk',
         all(os.path.isdir(os.path.join(PKG, 'archetypes', k)) for k in UI.ACTIVE),
         'an active kind with no archetype would fail at the first plan')


def group_tier(s):
    s.eq('UI-15', 'an empty place with nothing named is light', UI.honest_tier(0, False), 'light')
    s.eq('UI-16', 'naming the first artefact lifts it to standard',
         UI.honest_tier(0, True), 'standard')
    s.eq('UI-17', 'a large vault reaches governed', UI.honest_tier(150, False), 'governed')

    opts = {t['tier']: t for t in UI.tier_options(0, False)}
    s.ok('UI-18', 'an unsupported tier is shown with what would lift it',
         not opts['standard']['supported'] and '20 needed' in opts['standard']['blocked'],
         'hiding it would leave the operator guessing what the refusal wants')
    named = {t['tier']: t for t in UI.tier_options(0, True)}
    s.ok('UI-19', 'naming the artefact makes standard selectable',
         named['standard']['supported'])


def group_page(s):
    html = UI.render_page(PKG, key='a-key')
    s.ok('UI-20', 'the page ships its data rather than its placeholder', '{{DATA}}' not in html)
    s.contains('UI-21', 'the key the page must send back is embedded', html, 'a-key')

    missing = UI.count_vault(os.path.join(tempfile.gettempdir(), 'solai-no-such-dir-xyz'))
    s.ok('UI-22', 'a path that is not there is reported, not raised',
         missing['exists'] is False and missing['content'] == 0)

    here = UI.count_vault(os.path.join(PKG, 'archetypes'))
    s.ok('UI-23', 'a real path is counted', here['exists'] and here['files'] > 0)

    s.contains('UI-27', 'the folder new places are suggested under reaches the page',
               UI.render_page(PKG, key='k', base='C:/vaults'), 'C:/vaults')
    s.ok('UI-28', 'the suggested folder is never inside the package',
         not UI.default_base().startswith(PKG),
         'suggesting a folder inside the tool is worse than suggesting home')

    named = UI.render_page(PKG, key='k')
    s.ok('UI-29', 'the page carries its own name in the tab and the wordmark',
         '<title>Solai</title>' in named and '>Solai</h1>' in named,
         'engine, command and page carry one name')
    s.eq('UI-30', 'the surface never states a version of its own',
         UI.VERSION, __import__('lib').VERSION)

    s.ok('UI-38', 'the dashboard is served by this process, not linked as a file',
         "'/dashboard?key='" in UI.render_page(PKG, key='k')
         and 'file:///' not in UI.render_page(PKG, key='k'),
         'a browser silently refuses to follow a file:// link from an http:// page')

    page = UI.render_page(PKG, key='k')
    s.ok('UI-41', 'the rail has one entry per step, numbered in order, and each has a section',
         all(('data-step="%d"' % n) in page and ('id="s%d"' % n) in page
             for n in range(1, 7)) and 'data-step="7"' not in page,
         'renumbering the steps and forgetting the rail is the obvious way to break this')

    s.ok('UI-43', 'every rail step is reachable without a mouse',
         all(('data-step="%d" tabindex="0" role="button"' % n) in page for n in range(1, 7)),
         'the rail scrolls the page, so it is a control and has to answer a keyboard')

    s.ok('UI-44', 'the types it does not build have a region of their own',
         'id="types-off"' in page and 'id="types-off-wrap"' in page
         and page.index('id="types"') < page.index('id="types-off"'),
         'sharing one grid gave the three it cannot build the top row and orphaned the one '
         'it can')

    argv = UI.start_argv('C:/vaults/My Place')
    s.ok('UI-39', 'the session opens in the place, quoted for a path with spaces in it',
         argv[0] == 'powershell' and '-NoExit' in argv
         and "-LiteralPath 'C:" in argv[-1] and '; claude ' in argv[-1],
         repr(argv))

    s.ok('UI-42', 'the session is handed its first instruction rather than a blank prompt',
         'START-HERE.md' in UI.FIRST_PROMPT and 'Write nothing yet' in UI.FIRST_PROMPT
         and UI.FIRST_PROMPT in argv[-1].replace("''", "'"),
         'a terminal at a blank prompt asks the person to know what to type')

    s.ok('UI-40', "a quote in a folder name cannot end the quoting",
         "''" in UI.start_argv("C:/vaults/Bob's place")[-1],
         repr(UI.start_argv("C:/vaults/Bob's place")[-1]))

    tok = UI.answer_token('C:/x', 'role', ANS)
    s.ok('UI-31', 'the materials path is part of the fingerprint a plan is approved for',
         UI.answer_token('C:/x', 'role', ANS, 'C:/docs') != tok
         and UI.answer_token('C:/x', 'role', ANS, 'C:/docs')
         != UI.answer_token('C:/x', 'role', ANS, 'C:/other'),
         'a plan shown for one folder of documents may not be spent on another')

    s.ok('UI-33', 'the native dialog is a separate stdlib script the surface shells out to',
         os.path.exists(os.path.join(PKG, 'skills', 'solai-scaffold', 'pick.py'))
         and UI.pick_argv('folder')[-1] == 'folder',
         'Tk wants the main thread; the server answers on worker threads')

    s.raises('UI-34', 'a dialog kind the picker does not have is refused, not defaulted',
             lambda: UI.pick_argv('everything'), 'unknown kind')

    s.eq('UI-35', 'one path per line, so a multi-file pick reaches the engine as several flags',
         [a for a in UI.engine_argv('C:/x', 'role', ANS, False, 'C:/a\nC:/b')
          if a in ('--materials', 'C:/a', 'C:/b')],
         ['--materials', 'C:/a', '--materials', 'C:/b'])

    with_mats = UI.engine_argv('C:/x', 'role', ANS, False, 'C:/docs')
    s.ok('UI-32', 'the materials path reaches the engine as a flag, and only when given',
         with_mats[with_mats.index('--materials') + 1] == 'C:/docs'
         and '--materials' not in UI.engine_argv('C:/x', 'role', ANS),
         repr(with_mats))


GROUPS = (group_declarations, group_gate, group_argv, group_tier, group_page)
