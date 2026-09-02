# -*- coding: utf-8 -*-
"""Solai - the setup surface: a local page driving the same engine the command line does.

One name for the whole thing: Solai is the engine, the command and this page. It says
«just so» in Kazakh - what you call the answer when what was declared and what was built
turn out to be the same, which is what every gate here spends its run establishing.

    py serve.py [--port 0] [--vaults "<folder new vaults go under>"] [--no-browser]

Why a server and not a page. A file opened from disk cannot create a directory, and a page
published to the web cannot touch this machine at all. The only honest way for a button
labelled `create` to create something is for the page to be served by a process that has the
filesystem, so this is a single stdlib process bound to the loopback interface, holding a
key generated at boot, printed once, and required on every request.

What it does NOT do. It does not build a plan, it does not decide a tier, and it does not
write a file. Every one of those is a `scaffold.py` call whose output is relayed to the page
verbatim, refusals included. This module owns three things only: which questions the
archetype declares, what is already on disk at the path, and the rule that `create` cannot
run for an answer set no plan has been shown for.

That last rule is the reason this file exists rather than a form posting straight to the
engine. `--plan` before `--apply` was a sentence in a skill file that a person had to keep;
here changing any answer voids the token and the button goes back to being unavailable.
"""
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(HERE))
for p in (PKG,):
    if p not in sys.path:
        sys.path.insert(0, p)

from lib import VERSION, decl, engine, fsplan                       # noqa: E402

# The version is the package's, read from `lib` rather than restated here. A surface
# carrying its own number is a second source of truth for the same fact.
SCAFFOLD = os.path.join(HERE, 'scaffold.py')
PICK = os.path.join(HERE, 'pick.py')
UI = os.path.join(HERE, 'ui.html')

# The browser asks for /favicon.ico whether or not anything serves one, and a 404 in the log of
# a five-minute setup process reads like a fault when it is a tab icon. Serve the mark instead:
# the page links to this route, so the icon and the log line have one source.
FAVICON = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<rect width='32' height='32' rx='7' fill='#14161a'/>"
    "<circle cx='16' cy='13' r='5.5' fill='#e0b46c'/>"
    "<path d='M16 20v6' stroke='#e0b46c' stroke-width='3' stroke-linecap='round'/>"
    "</svg>"
)

# The tier table of `skills/solai/interview.md`, in the one form a page can render. Kept as
# data rather than prose because the page has to grey out what the counts do not support,
# and a rule that is only prose cannot grey anything out.
TIERS = (
    ('minimal', 0, 'Nothing to maintain: a CLAUDE.md, a change log, an inbox.'),
    ('light', 0, 'The honest tier for a vault nobody has written in yet.'),
    ('standard', 20, 'Needs 20 content files, or a named first artefact with a date.'),
    ('governed', 150, 'Needs 150 content files. Units and an impact index earn their keep '
                      'at that size and not before.'),
)

# Which types this surface offers today. A type left out is shown and disabled with the
# reason, never hidden: hiding it would make the page a smaller claim about what the package
# builds than the package makes, and the command line builds all four either way. This is a
# decision about the surface, not about the declarations, which is why it lives here and not
# in a manifest.
ACTIVE = ('role',)
DEACTIVATED = 'Not offered here yet. The command line builds it.'

# Answers the page collects but the engine does not take, and the reason each one is shown
# as a statement rather than a control. A control that changes nothing is the machinery D1
# forbids: it asserts a capability with nothing behind it.
INERT = {
    'mode': ('greenfield',
             'This surface builds a new vault. Reading an existing one is `/solai adopt`, '
             'which writes nothing and reports where it stands.'),
    'output_language': ('English',
                        'This surface builds vaults that are run in English: their '
                        'instructions, headings and generated prose. Content is a separate '
                        'answer below. The command line takes `output_language=ru` for a '
                        'vault whose own files are Russian.'),
    'partition': ('set later, not at setup',
                  'The codes are whatever areas the work turns out to have, and they read out '
                  'of the obligations once those exist. Guessed now, the guess sits in every '
                  'card that follows. The command line takes it for a vault that already '
                  'knows its own divisions.'),
    'classes': ('declared by the archetype',
                'Class selection is an authoring change, made in the archetype manifest with '
                'a change record, not a setup answer.'),
}


# --------------------------------------------------------------------------- declarations

def archetypes(pkg=PKG):
    """Every archetype on disk, as the page needs it. Read from the manifests each time the
    page loads, so a manifest edit shows up without touching this file."""
    root = os.path.join(pkg, 'archetypes')
    out = []
    for name in sorted(os.listdir(root)):
        if not os.path.isdir(os.path.join(root, name)):
            continue
        try:
            arch = decl.load_archetype(pkg, name)
        except decl.DeclError as e:
            out.append({'name': name, 'broken': '\n'.join(e.errors)})
            continue
        out.append({
            'name': arch.name,
            'title': arch.title,
            'summary': arch.summary,
            'active': arch.name in ACTIVE,
            'deactivated': '' if arch.name in ACTIVE else DEACTIVATED,
            'asks': list(arch.asks),
            'defaults': dict(arch.defaults),
            'tier': arch.default_tier,
            'classes': list(arch.class_names),
            'agents': list(arch.agent_names),
            'workflows': list(arch.workflow_names),
            'folders': [f.get('path', '') for f in arch.folders],
            # `binds` names the field the codes land in, and the page labels the input
            # with it. Dropping it here is how the label read `Tracks` in a vault that has
            # areas: the surface was defaulting where the declaration had an answer.
            'partition': {'prompt': arch.partition.get('prompt', ''),
                          'binds': arch.partition.get('binds', ''),
                          'example': list(arch.partition.get('example', []))},
        })
    return out


# --------------------------------------------------------------------------- the path

def count_vault(root):
    """What is already at the path. Counted before anything is asked, which is step 1 of the
    interview and the step a tool that hands down a tier without it is skipping."""
    root = os.path.abspath(root)
    info = {'root': root, 'exists': fsplan.exists(root), 'parent_exists': False,
            'files': 0, 'folders': 0, 'markdown': 0, 'frontmatter': 0, 'skills': 0,
            'content': 0, 'last_edit': '', 'built_by_place': False}
    info['parent_exists'] = fsplan.exists(os.path.dirname(root))
    if not info['exists']:
        return info
    newest = 0.0
    for dirpath, dirnames, filenames in os.walk(fsplan.w(root)):
        dirnames[:] = [d for d in dirnames if d not in ('.git', 'node_modules', '.obsidian')]
        info['folders'] += len(dirnames)
        for fn in filenames:
            info['files'] += 1
            full = os.path.join(dirpath, fn)
            try:
                newest = max(newest, os.path.getmtime(full))
            except OSError:
                pass
            if fn.endswith('.md'):
                info['markdown'] += 1
                if fn == 'SKILL.md':
                    info['skills'] += 1
                try:
                    with open(full, 'r', encoding='utf-8', errors='replace') as fh:
                        if fh.read(4).startswith('---'):
                            info['frontmatter'] += 1
                except OSError:
                    pass
    if newest:
        import datetime
        info['last_edit'] = datetime.date.fromtimestamp(newest).isoformat()
    info['content'] = engine.count_content(root)
    info['built_by_place'] = fsplan.exists(os.path.join(root, '_system', 'os', 'vault.md'))
    return info


def tier_options(content, named):
    """The tier list with each entry marked supported or not, and the requirement spelled out
    where it is not. The interview says not to offer a tier the counts do not support: an
    offer implies the choice is reasonable, so an unsupported tier is shown refused rather
    than hidden, which also tells the operator what would lift it."""
    out = []
    for name, need, why in TIERS:
        ok = True
        blocked = ''
        if need and content < need and not (named and name == 'standard'):
            ok = False
            blocked = ('%d content files here, %d needed%s.'
                       % (content, need,
                          ' - or name the first artefact and its date' if name == 'standard'
                          else ''))
        out.append({'tier': name, 'supported': ok, 'why': why, 'blocked': blocked})
    return out


def honest_tier(content, named):
    """The tier the counts support, which is what the page selects by default."""
    if content >= 150:
        return 'governed'
    if content >= 20 or named:
        return 'standard'
    return 'light'


# --------------------------------------------------------------------------- the engine

def engine_answers(answers):
    """The answers that reach the engine: the inert ones are statements on the page and an
    empty one is not an answer. Filtering here rather than in the request handler is what
    lets the fingerprint and the command line be built from the same set."""
    return {k: v for k, v in (answers or {}).items()
            if k not in INERT and v not in (None, '')}


def answer_token(root, archetype, answers, materials=''):
    """A fingerprint of exactly what would be built. `create` is refused unless a plan for
    this fingerprint has been shown in this session, so editing any field after the plan
    puts the button back to unavailable rather than leaving a stale approval standing.

    The materials path is part of it. It decides rows in the plan, so a plan approved for one
    folder of documents may not be spent on another."""
    blob = json.dumps([os.path.abspath(root), archetype, engine_answers(answers),
                       materials or ''], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]


# Held while a native dialog is open. Tk gives no way to raise a second one usefully, and
# a request waiting on a window nobody can see is the worst of both.
PICKING = threading.Lock()


class PlanGate(object):
    """`--plan` before `--apply`, held by something other than a person's memory.

    A token is admitted only by a plan that the engine returned cleanly, and it is spent by
    the apply that uses it. Spending it matters as much as granting it: an apply that failed
    halfway must be planned again against what is now on disk, and a second identical apply
    is a different act from the first even when the answers have not moved.
    """

    def __init__(self):
        self.tokens = set()

    def remember(self, token):
        self.tokens.add(token)

    def forget(self, token):
        self.tokens.discard(token)

    def allows(self, token):
        return token in self.tokens


def material_paths(materials):
    """One field, one path per line. The native picker can return several files at once and a
    person can paste a list, and both arrive here as one string."""
    return [p.strip() for p in (materials or '').splitlines() if p.strip()]


# ------------------------------------------------------------------------------- Obsidian

# Obsidian keeps its vault list in one file, %APPDATA%\obsidian\obsidian.json, and offers no
# command that adds to it: the obsidian:// URI opens a vault the app already knows and does
# nothing for a folder it does not, and the desktop binary takes a URI rather than a path. So
# opening a vault that was created a minute ago means writing the entry the app would have
# written, then asking the app to open it.
REGISTRY = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'),
                        'obsidian', 'obsidian.json')


def obsidian_vaults(registry=None):
    """The vault list as {id: entry}. A missing file, an unreadable one and one holding some
    other shape all mean the same thing here - Obsidian has nothing to say about this machine
    yet - so they answer alike rather than raising."""
    try:
        with open(registry or REGISTRY, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    vaults = data.get('vaults') if isinstance(data, dict) else None
    return vaults if isinstance(vaults, dict) else {}


def obsidian_id(root, registry=None):
    """The id Obsidian already holds for this folder, or None. Compared the way the filesystem
    compares - case folded, separators normalised - because the registry holds whatever was
    typed the day the vault was added, and a OneDrive path gets retyped."""
    want = os.path.normcase(os.path.normpath(os.path.abspath(root)))
    for vid, entry in obsidian_vaults(registry).items():
        have = entry.get('path') if isinstance(entry, dict) else None
        if have and os.path.normcase(os.path.normpath(os.path.abspath(have))) == want:
            return vid
    return None


def obsidian_running():
    """Whether the app is up, because it rewrites its vault list from memory when it closes.
    An entry added behind a running instance is an entry that may be thrown away an hour
    later, and a button that loses its work quietly is worse than one that says it cannot."""
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Obsidian.exe', '/NH'],
                             capture_output=True, text=True,
                             encoding='utf-8', errors='replace').stdout
    except OSError:
        return False
    return 'Obsidian.exe' in (out or '')


def obsidian_register(root, registry=None):
    """Add the folder to the vault list once. Returns (id, added), where added is false when
    the folder was already listed, so a second press is not a second entry for one vault.

    Written beside itself and moved into place: a failure halfway leaves the list Obsidian had
    rather than half a list, which is the one outcome this cannot risk."""
    path = registry or REGISTRY
    known = obsidian_id(root, path)
    if known:
        return known, False
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    vaults = data.get('vaults')
    if not isinstance(vaults, dict):
        vaults = {}
        data['vaults'] = vaults
    vid = os.urandom(8).hex()
    while vid in vaults:
        vid = os.urandom(8).hex()
    vaults[vid] = {'path': os.path.abspath(root), 'ts': int(time.time() * 1000)}
    folder = os.path.dirname(os.path.abspath(path))
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    temp = path + '.solai'
    with open(temp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(temp, path)
    return vid, True


def obsidian_uri(root):
    """Keyed on path rather than name: the name is whatever the folder is called, two vaults on
    one machine can share it, and the path is what the registry is keyed on."""
    return 'obsidian://open?path=' + urllib.parse.quote(os.path.abspath(root), safe='')


def open_obsidian(root):
    """Hand the URI to the machine and let it start or reuse the app. os.startfile is the
    Windows way and takes no shell; the fallback keeps this module importable, and testable,
    where that call does not exist."""
    uri = obsidian_uri(root)
    starter = getattr(os, 'startfile', None)
    if starter:
        starter(uri)
    else:
        subprocess.Popen(['cmd', '/c', 'start', '', uri], close_fds=True)
    return uri


# The first thing said in a new vault. A terminal opened at a blank prompt asks the person
# to know what to type, which is the one thing they cannot know a minute after pressing
# create. It orients and stops: nothing is written until they say so.
FIRST_PROMPT = (
    "Read START-HERE.md and CLAUDE.md in this folder, and list what is in _inbox/. "
    "Then tell me in five lines: what this vault is for, what is waiting to be read, and "
    "what the first move is. Write nothing yet."
)


def start_argv(root, prompt=FIRST_PROMPT):
    """The command that opens a session in a vault, as a list rather than a string.

    PowerShell because that is the shell on this machine, `-NoExit` so the window survives
    whatever happens next, and `Set-Location -LiteralPath` because vault paths carry spaces,
    Cyrillic and the occasional bracket, and `cd` with a bare path eventually meets one it
    reads as a pattern. The prompt is passed to `claude` as its opening message, so the
    session starts with something on the screen rather than a cursor.
    """
    root = os.path.abspath(root)
    return ['powershell', '-NoExit', '-NoLogo', '-Command',
            'Set-Location -LiteralPath %s; claude %s'
            % (_ps_quote(root), _ps_quote(prompt))]


def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def pick_argv(kind='folder'):
    if kind not in ('folder', 'files'):
        raise ValueError('unknown kind %r. Say folder or files.' % kind)
    return [sys.executable, PICK, kind]


def engine_argv(root, archetype, answers, apply_it=False, materials=''):
    argv = [sys.executable, SCAFFOLD, root, '--archetype', archetype]
    for p in material_paths(materials):
        argv += ['--materials', p]
    argv.append('--answers')
    for k in sorted(answers):
        v = answers[k]
        if v not in (None, ''):
            argv.append('%s=%s' % (k, v))
    if apply_it:
        argv.append('--apply')
    return argv


def run_engine(root, archetype, answers, apply_it=False, materials=''):
    """One subprocess, output relayed whole. A refusal is the engine's sentence, not this
    module's summary of it: relaying it as written is the difference between a gate and a
    suggestion."""
    proc = subprocess.run(engine_argv(root, archetype, answers, apply_it, materials),
                          capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (proc.stdout or '') + (proc.stderr or '')
    return {'code': proc.returncode, 'output': out,
            'refused': '\nrefused:' in out or '\nerrors:' in out,
            'applied': '\napplied.' in out}


# --------------------------------------------------------------------------- the page

def default_base(argv_base=''):
    """Where a new vault is suggested to go, so the path field is a correction rather than a
    blank. `--vaults` wins; otherwise the folder holding this session's working directory,
    which is where the other vaults on a machine like this one already sit; otherwise home.

    Only a suggestion. The field is editable and the engine reads the field, not this.
    """
    if argv_base:
        return os.path.abspath(argv_base)
    parent = os.path.dirname(os.path.abspath(os.getcwd()))
    # Started from inside the package, which is where it is debugged from and never where a
    # vault belongs. Suggesting a folder inside the tool would be worse than suggesting home.
    if parent.startswith(PKG) or not os.path.isdir(parent):
        return os.path.expanduser('~')
    return parent



def render_page(pkg=PKG, key='', base=''):
    with open(UI, 'r', encoding='utf-8') as fh:
        html = fh.read()
    data = {'version': VERSION, 'package': pkg, 'key': key, 'base': base or default_base(),
            'archetypes': archetypes(pkg), 'inert': INERT,
            'tiers': [{'tier': t[0], 'needs': t[1], 'why': t[2]} for t in TIERS]}
    return html.replace('{{DATA}}', json.dumps(data, ensure_ascii=False))


class Handler(BaseHTTPRequestHandler):

    server_version = 'solai/' + VERSION
    key = ''
    base = ''
    gate = PlanGate()

    def log_message(self, fmt, *args):                              # quieter than the default
        sys.stderr.write('  %s\n' % (fmt % args))

    # ---------------------------------------------------------------- plumbing

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        raw = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def _authorised(self):
        if self.headers.get('X-Solai-Key', '') == self.key:
            return True
        # The key may be the only parameter or one of several, so match it as a parameter
        # rather than as the tail of the string.
        return ('?key=' + self.key) in self.path or ('&key=' + self.key) in self.path

    def _body(self):
        n = int(self.headers.get('Content-Length', 0) or 0)
        return json.loads(self.rfile.read(n).decode('utf-8')) if n else {}

    # ---------------------------------------------------------------- routes

    def do_GET(self):
        route = self.path.split('?')[0]
        if route == '/favicon.ico':
            # No key: it is a tab icon, the same bytes for anyone who can reach the loopback
            # port, and gating it would only turn the 404 into a 403.
            return self._send(200, FAVICON, 'image/svg+xml; charset=utf-8')
        if route == '/dashboard':
            # Chrome refuses to follow a file:// link from an http:// page, silently, which is
            # why the button did nothing. The dashboard is a file on this machine and this is
            # a process on this machine, so it serves it rather than asking the browser to.
            if not self._authorised():
                return self._send(403, '{"error":"bad key"}')
            import urllib.parse as _u
            q = _u.parse_qs(self.path.split('?', 1)[1] if '?' in self.path else '')
            root = (q.get('root') or [''])[0]
            page = os.path.join(os.path.abspath(root), 'dashboard.html')
            body = fsplan.read(page)
            if body is None:
                return self._send(404, 'No dashboard at %s. It is written when the vault is '
                                       'created.' % page, 'text/plain; charset=utf-8')
            return self._send(200, body, 'text/html; charset=utf-8')
        if route != '/':
            return self._send(404, '{"error":"no such path"}')
        if not self._authorised():
            return self._send(403, 'The key in the URL does not match this process. Use the '
                                   'link the server printed.', 'text/plain; charset=utf-8')
        self._send(200, render_page(PKG, self.key, self.base), 'text/html; charset=utf-8')

    def do_POST(self):
        if not self._authorised():
            return self._send(403, '{"error":"bad key"}')
        route = self.path.split('?')[0]
        try:
            body = self._body()
        except ValueError:
            return self._send(400, '{"error":"body was not json"}')
        try:
            payload = self.route(route, body)
        except Exception as err:                                    # noqa: BLE001
            return self._send(500, json.dumps({'error': '%s: %s' % (type(err).__name__, err)}))
        if payload is None:
            return self._send(404, '{"error":"no such route"}')
        code, data = payload
        self._send(code, json.dumps(data, ensure_ascii=False))

    def route(self, route, body):
        root = body.get('root', '')
        if route == '/api/count':
            info = count_vault(root)
            named = bool(body.get('first_artefact'))
            info['honest_tier'] = honest_tier(info['content'], named)
            info['tiers'] = tier_options(info['content'], named)
            return 200, info

        if route == '/api/start':
            # A terminal, in that folder, with the session already starting. The vault's
            # skills exist only inside it, so anywhere else is the wrong window.
            here = os.path.abspath(root)
            if not fsplan.exists(here):
                return 400, {'error': 'no such folder: %s' % here}
            flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
            subprocess.Popen(start_argv(here), creationflags=flags, close_fds=True)
            return 200, {'started': True, 'root': here}

        if route == '/api/obsidian':
            # A button of its own rather than a second thing the session button does, because
            # these two fail apart: Obsidian can be absent or mid-update while the terminal is
            # fine, and one press losing both would be this surface's fault, not the machine's.
            here = os.path.abspath(root)
            if not fsplan.exists(here):
                return 400, {'error': 'no such folder: %s' % here}
            known = obsidian_id(here)
            if not known and obsidian_running():
                return 200, {'opened': False, 'note':
                             'Obsidian is open, and it rewrites its vault list when it closes, '
                             'so this did not touch the list. In Obsidian: Open folder as '
                             'vault, and pick %s. This button opens it after that.' % here}
            added = False
            if not known:
                try:
                    _, added = obsidian_register(here)
                except OSError as err:
                    return 200, {'opened': False, 'note':
                                 'the vault list could not be written (%s). In Obsidian: Open '
                                 'folder as vault, and pick %s.' % (err, here)}
            open_obsidian(here)
            return 200, {'opened': True, 'registered': added, 'root': here}

        if route == '/api/pick':
            # The dialog belongs to this machine, not to the page: a browser hands a page
            # bytes and never a path, and this surface copies from where the documents
            # already are. One at a time - a second dialog behind the first is a hang the
            # operator cannot see.
            if not PICKING.acquire(blocking=False):
                return 409, {'error': 'a dialog is already open on this machine.'}
            try:
                proc = subprocess.run(pick_argv(body.get('kind') or 'folder'),
                                      capture_output=True, text=True,
                                      encoding='utf-8', errors='replace')
            finally:
                PICKING.release()
            if proc.returncode != 0:
                return 200, {'error': (proc.stderr or 'the dialog failed').strip()}
            chosen = (proc.stdout or '').strip()
            return 200, {'path': chosen, 'cancelled': not chosen}

        if route == '/api/materials':
            # Counts what would be copied and relays the engine's own refusals. It does not
            # open a single file: reading them is the first session's job, with an agent that
            # can be checked, not this process's.
            given = material_paths(body.get('materials'))
            if not given:
                return 200, {'files': 0, 'errors': []}
            found, errs = engine.collect_materials(given, root or os.getcwd())
            # The name shown is the one the file takes inside the inbox, not its basename: a
            # mirrored subfolder is the reason two documents of one name can both be here.
            return 200, {'files': len(found), 'errors': errs,
                         'names': [rel for _, rel in found[:12]]}

        if route == '/api/mkdir':
            root = os.path.abspath(root)
            if fsplan.exists(root):
                return 200, {'created': False, 'root': root}
            if not fsplan.exists(os.path.dirname(root)):
                return 400, {'error': 'the parent folder does not exist: %s'
                                      % os.path.dirname(root)}
            os.makedirs(fsplan.w(root))
            return 200, {'created': True, 'root': root}

        if route in ('/api/plan', '/api/apply'):
            archetype = body.get('archetype', '')
            if archetype not in ACTIVE:
                # The page disables these, so a request for one arrives only from something
                # other than the page. A surface that says deactivated in one place and
                # builds it anyway in another has told the operator a falsehood.
                return 400, {'error': 'the %r kind is not offered by this surface. %s'
                                      % (archetype, DEACTIVATED)}
            answers = engine_answers(body.get('answers'))
            materials = (body.get('materials') or '').strip()
            token = answer_token(root, archetype, answers, materials)
            if route == '/api/apply' and not self.gate.allows(token):
                return 409, {'error': 'no plan has been shown for these answers. Plan first.',
                             'token': token}
            res = run_engine(root, archetype, answers, apply_it=(route == '/api/apply'),
                             materials=materials)
            if route == '/api/plan' and res['code'] == 0 and not res['refused']:
                self.gate.remember(token)
            else:
                self.gate.forget(token)
            res['token'] = token
            res['ready'] = self.gate.allows(token)
            return 200, res
        return None


def serve(port=0, open_browser=True, base=''):
    key = hashlib.sha256(os.urandom(32)).hexdigest()[:20]
    Handler.key = key
    Handler.base = default_base(base)
    Handler.gate = PlanGate()
    # Threading, because one request can now be a dialog waiting on a person. On a single
    # thread that dialog would hold the only one answering the page, and the page would
    # look dead while the window it opened sat in front of the operator.
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = 'http://127.0.0.1:%d/?key=%s' % (httpd.server_port, key)
    print('Solai   setup surface %s' % VERSION)
    print('  %s' % url)
    print('  new vaults suggested under %s' % Handler.base)
    print('  loopback only, one key per process. Ctrl-C to stop.')
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n  stopped.')
    return 0


def main():
    argv = sys.argv[1:]
    port = 0
    base = ''
    if '--port' in argv:
        port = int(argv[argv.index('--port') + 1])
    if '--vaults' in argv:
        base = argv[argv.index('--vaults') + 1]
    return serve(port=port, open_browser='--no-browser' not in argv, base=base)


if __name__ == '__main__':
    sys.exit(main())
