# -*- coding: utf-8 -*-
"""Assert the vault against its own declarations.

    py _system/scripts/validate_cards.py <vault-root> [--json] [--family CL,LK]

Declaration-driven, never generated. The engine emits DATA; this reads the compiled class
declarations in `_system/os/classes/*.toml` at runtime and dispatches. Generating a
validator per vault would mean generating code nobody tests.

Severity, inherited unchanged from the vault this pattern came from:

    BLOCKER  must be zero. Exit 1
    GATE     blocks a structural change. A run may complete with them recorded and accepted
    WARN     reported only

Families:

    CL  card shape: filename, id, type, required fields, enum values, status, body headings
    LK  links: targets resolve, reciprocals present, lateral stays same-class
    ID  identifiers: unique, contiguous, one minter per prefix
    GN  generated files: stamped, and the stamp still matches
    VC  closed vocabularies: no undeclared frontmatter key
    ST  status protocol: terminal cards carry their callout
    AV  anti-avoidance: the documents-to-artefacts ratio, reported not enforced

An assertion that cannot be checked mechanically is listed as NOT ENFORCED rather than
quietly dropped. A validator that reports only what it can measure, without saying what it
cannot, is claiming coverage it does not have.
"""
import io
import json
import os
import re
import sys
import tomllib

sys.stdout.reconfigure(encoding='utf-8')

BLOCKER, GATE, WARN = 'BLOCKER', 'GATE', 'WARN'
SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules', '__pycache__'}

NOT_ENFORCED = [
    ('CL-9', 'a derived field was not hand-set since the last derive run',
     'needs the deriving script to record its own last run'),
    ('VC-6', 'the reason a suppression was granted is still true',
     'a human judgement about the world, not about the files'),
    ('AV-6', 'whether the work chosen was next, or merely safe',
     'the counsel verdict answers this; the validator does not pretend to'),
]


# --------------------------------------------------------------------------- reading

def split_fm(text):
    if not text.startswith('---'):
        return None, text
    nl = text.find('\n')
    if nl == -1 or text[3:nl].strip():
        return None, text
    end = text.find('\n---', nl)
    while end != -1:
        after = end + 4
        if after >= len(text) or text[after] in '\r\n':
            return text[nl + 1:end], text[after:].lstrip('\r\n')
        end = text.find('\n---', end + 1)
    return None, text


def fm_scalar(fm, key):
    if not fm:
        return None
    m = re.search(r'^%s:[ \t]*(.*?)[ \t]*$' % re.escape(key), fm, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    return v.strip('"\'') if v else None


def fm_list(fm, key):
    """Inline `[a, b]` or a block list. Returns None when the key is absent."""
    if not fm:
        return None
    m = re.search(r'^%s:[ \t]*(.*?)[ \t]*$' % re.escape(key), fm, re.M)
    if not m:
        return None
    rest = m.group(1).strip()
    if rest.startswith('[') and rest.endswith(']'):
        inner = rest[1:-1].strip()
        return [x.strip().strip('"\'') for x in inner.split(',')] if inner else []
    out, started = [], False
    for line in fm.split('\n'):
        if re.match(r'^%s:' % re.escape(key), line):
            started = True
            continue
        if started:
            if line.startswith((' ', '\t')):
                im = re.match(r'^\s*-\s+(.*?)\s*$', line)
                if im:
                    out.append(im.group(1).strip().strip('"\''))
            elif line.strip():
                break
    return out


def fm_keys(fm):
    if not fm:
        return []
    return re.findall(r'^([A-Za-z_][A-Za-z0-9_.-]*):', fm, re.M)


def wl_target(value):
    m = re.match(r'^\[\[([^\]|#]+)', str(value).strip())
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------- model

class Decl(object):
    def __init__(self, data):
        self.name = data.get('class')
        self.prefix = data.get('prefix')
        self.folder = data.get('folder')
        self.skill = data.get('skill') or self.name
        self.minted_by = data.get('minted_by')
        st = data.get('status', {})
        self.lifecycle = st.get('lifecycle', [])
        self.terminal = st.get('terminal', [])
        self.rules = st.get('rules', {})
        self.fields = data.get('fields', [])
        self.links = data.get('links', [])
        body = data.get('body', {})
        self.required_h2 = body.get('required_h2', [])

    @property
    def statuses(self):
        return list(self.lifecycle) + list(self.terminal)


def load_decls(root):
    d = os.path.join(root, '_system', 'os', 'classes')
    out = {}
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if not name.endswith('.toml'):
            continue
        with open(os.path.join(d, name), 'rb') as fh:
            c = Decl(tomllib.load(fh))
        if c.name:
            out[c.name] = c
    return out


def load_cards(root, decls):
    cards = {}
    for c in decls.values():
        folder = os.path.join(root, c.folder.replace('/', os.sep))
        if not os.path.isdir(folder):
            continue
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
            for name in sorted(filenames):
                if not name.endswith('.md'):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    with io.open(path, encoding='utf-8') as fh:
                        text = fh.read()
                except (OSError, UnicodeDecodeError):
                    continue
                fm, body = split_fm(text)
                rel = os.path.relpath(path, root).replace(os.sep, '/')
                cards[rel] = {'class': c, 'fm': fm, 'body': body, 'name': name,
                              'stem': os.path.splitext(name)[0],
                              'archived': '/archive/' in rel}
    return cards


# --------------------------------------------------------------------------- families

def fam_CL(cards, decls, add):
    for rel, card in cards.items():
        c, fm, body = card['class'], card['fm'], card['body']
        rx = r'^%s-\d{3}$' % c.prefix
        if not re.match(rx, card['stem']):
            add('CL-1', BLOCKER, rel, 'filename is not %s-NNN' % c.prefix)
            continue
        if fm is None:
            add('CL-2', BLOCKER, rel, 'no frontmatter')
            continue
        if fm_scalar(fm, 'type') != c.name:
            add('CL-2', BLOCKER, rel, 'type is %r, expected %r'
                % (fm_scalar(fm, 'type'), c.name))
        if fm_scalar(fm, 'id') != card['stem']:
            add('CL-3', BLOCKER, rel, 'id %r does not match the filename'
                % fm_scalar(fm, 'id'))
        status = fm_scalar(fm, 'status')
        if c.statuses:
            if status is None:
                add('CL-6', BLOCKER, rel, 'no status')
            elif status not in c.statuses:
                add('CL-6', BLOCKER, rel, 'status %r is not one of %s'
                    % (status, ', '.join(c.statuses)))
        terminal = status in c.terminal
        relax = terminal and c.rules.get('terminal_relaxes_schema')
        for f in c.fields:
            if f.get('derived_by') or not f.get('required') or relax:
                continue
            val = fm_scalar(fm, f['name'])
            if val in (None, ''):
                add('CL-4', BLOCKER, rel, 'required field %r is missing or empty' % f['name'])
            elif f.get('values') and val not in f['values']:
                add('CL-5', BLOCKER, rel, '%s is %r, not one of %s'
                    % (f['name'], val, ', '.join(f['values'])))
        for f in c.fields:
            if f.get('derived_by') or f.get('required') or relax:
                continue
            val = fm_scalar(fm, f['name'])
            if val and f.get('values') and val not in f['values']:
                # `Unknown` here is the commonest way this fires: the body-heading
                # rule gets applied to a field. An optional field is left empty.
                hint = ('. This field is optional: leave it empty rather than writing '
                        '%r. The `Unknown` convention is for body headings only' % val
                        if val.lower() in ('unknown', 'n/a', 'none', 'tbd', '?') else '')
                add('CL-5', BLOCKER, rel, '%s is %r, not one of %s%s'
                    % (f['name'], val, ', '.join(f['values']), hint))
        if terminal and c.rules.get('terminal_callout'):
            first = next((l for l in body.split('\n') if l.strip()), '')
            if not first.strip().startswith('>'):
                add('CL-7', GATE, rel,
                    'terminal status %r but the body does not open with a callout naming '
                    'the reason and the date' % status)
        if not relax:
            for h in c.required_h2:
                if h not in body:
                    add('CL-8', GATE, rel, 'missing required heading %r' % h)


def fam_LK(cards, decls, add, all_stems):
    by_id = {}
    for rel, card in cards.items():
        by_id[card['stem']] = (rel, card)
    for rel, card in cards.items():
        c, fm = card['class'], card['fm']
        if fm is None:
            continue
        for l in c.links:
            vals = fm_list(fm, l['field'])
            if not vals:
                continue
            for v in vals:
                t = wl_target(v)
                if not t:
                    continue
                if t not in all_stems:
                    add('LK-2', BLOCKER, rel, 'link %s -> [[%s]] resolves to nothing'
                        % (l['field'], t))
                    continue
                if l.get('kind') == 'lateral':
                    other = by_id.get(t)
                    if other and other[1]['class'].name != c.name:
                        add('LK-3', GATE, rel, 'lateral link %s points at a %s'
                            % (l['field'], other[1]['class'].name))
                if l.get('kind') == 'bidirectional':
                    other = by_id.get(t)
                    if not other:
                        continue
                    back = fm_list(other[1]['fm'], l['reciprocal']) or []
                    if not any(wl_target(b) == card['stem'] for b in back):
                        add('LK-1', BLOCKER, rel,
                            '%s -> [[%s]] has no reciprocal %s.%s pointing back'
                            % (l['field'], t, l['target'], l['reciprocal']))


def fam_ID(cards, decls, add):
    minters = {}
    for c in decls.values():
        if c.prefix in minters and minters[c.prefix] != c.minted_by:
            add('ID-4', BLOCKER, c.folder, 'prefix %s is minted by two classes' % c.prefix)
        minters[c.prefix] = c.minted_by
    seen = {}
    for rel, card in cards.items():
        stem = card['stem']
        if stem in seen:
            add('ID-1', BLOCKER, rel, 'id %s also used by %s' % (stem, seen[stem]))
        seen[stem] = rel
    for c in decls.values():
        nums = sorted(int(s.split('-')[1]) for s in seen
                      if re.match(r'^%s-\d{3}$' % c.prefix, s))
        if not nums:
            continue
        missing = [n for n in range(1, max(nums) + 1) if n not in nums]
        if missing:
            add('ID-2', GATE, c.folder,
                '%s sequence has holes at %s. Legitimate if those were retired; record it'
                % (c.prefix, ', '.join('%03d' % m for m in missing[:8])))


def fam_GN(root, add):
    import hashlib

    def norm(t):
        t = t.replace('\r\n', '\n').replace('\r', '\n')
        return '\n'.join(l.rstrip() for l in t.split('\n')).rstrip('\n') + '\n'

    vol = [re.compile(p) for p in (r'^\s*columnSize:', r'^\s*viewport:')]

    def strip_vol(t):
        lines, keep, i = t.split('\n'), [], 0
        while i < len(lines):
            ln = lines[i]
            if any(r.search(ln) for r in vol):
                ind = len(ln) - len(ln.lstrip())
                i += 1
                while i < len(lines):
                    nx = lines[i]
                    if nx.strip() and (len(nx) - len(nx.lstrip())) <= ind:
                        break
                    i += 1
                continue
            keep.append(ln)
            i += 1
        return '\n'.join(keep)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(('.md', '.base')):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            try:
                with io.open(path, encoding='utf-8') as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            fm, body = split_fm(text)
            declared = fm_scalar(fm, 'body-sha')
            by = fm_scalar(fm, 'generated-by')
            if by and not declared:
                add('GN-1', BLOCKER, rel, 'says generated-by but carries no body-sha')
            if not declared:
                continue
            actual = hashlib.sha256(
                norm(strip_vol(body)).encode('utf-8')).hexdigest()[:16]
            if actual != declared:
                add('GN-2', BLOCKER, rel,
                    'hand-edited: the body no longer matches its stamp. The next '
                    'regeneration would discard the edit')


def fam_VC(root, cards, decls, add):
    p = os.path.join(root, '_system', 'vocabulary.md')
    if not os.path.exists(p):
        return
    with io.open(p, encoding='utf-8') as fh:
        vocab = fh.read()
    declared = set(re.findall(r'`([a-z][a-z0-9-]*)`', vocab))
    for rel, card in cards.items():
        for k in fm_keys(card['fm']):
            if k in declared:
                continue
            add('VC-2', GATE, rel, 'frontmatter key %r is not in the vocabulary' % k)
        for k in fm_keys(card['fm']):
            if '_' in k:
                add('VC-3', GATE, rel, 'key %r uses an underscore; keys are kebab-case' % k)


def fam_AV(root, cards, add):
    system = content = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d != '.claude']
        rel = os.path.relpath(dirpath, root).replace(os.sep, '/')
        for f in filenames:
            if not f.endswith('.md'):
                continue
            if rel.startswith('_system') or f == 'CLAUDE.md':
                system += 1
            else:
                content += 1
    # What actually left. A deliverable is shipped when it carries a date, never
    # because its status says so: a status is set by hand, a date has to be one.
    shipped = promised = 0
    for rel, card in cards.items():
        if getattr(card['class'], 'prefix', '') != 'DLV':
            continue
        promised += 1
        if (fm_scalar(card['fm'], 'sent-on') or '').strip():
            shipped += 1

    if content == 0 and system > 0:
        add('AV-2', GATE, '.',
            '%d system files, 0 content files. Nothing here has been written yet, so '
            'nothing here is finished. This is reported every run until it is not true'
            % system)
    elif content and system > content:
        add('AV-1', WARN, '.',
            'system %d to content %d. Machinery is outpacing the work it exists to serve'
            % (system, content))

    # AV-2 counts markdown, and markdown is easy to generate. A vault can silence
    # it by writing notes about itself without anything reaching a recipient, which
    # is the avoidance the family is named for. This counts the only honest number.
    if shipped == 0:
        add('AV-3', GATE, '.',
            '%d content files, %d deliverables promised, 0 sent. Nothing has left this '
            'place. Writing more of it will not change that number'
            % (content, promised))
    elif content > shipped * 20:
        add('AV-4', WARN, '.',
            '%d content files to %d sent. Documents are outpacing what leaves by more '
            'than twenty to one' % (content, shipped))

    return {'system': system, 'content': content,
            'promised': promised, 'shipped': shipped}


# --------------------------------------------------------------------------- main

def run(root, families=None):
    findings = []

    def add(aid, sev, where, msg):
        findings.append({'id': aid, 'severity': sev, 'where': where, 'message': msg})

    decls = load_decls(root)
    cards = load_cards(root, decls)
    all_stems = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            all_stems.add(os.path.splitext(f)[0])

    want = (lambda f: families is None or f in families)
    if want('CL'):
        fam_CL(cards, decls, add)
    if want('LK'):
        fam_LK(cards, decls, add, all_stems)
    if want('ID'):
        fam_ID(cards, decls, add)
    if want('GN'):
        fam_GN(root, add)
    if want('VC'):
        fam_VC(root, cards, decls, add)
    counts = fam_AV(root, cards, add) if want('AV') else {}
    return findings, {'classes': len(decls), 'cards': len(cards), 'counts': counts}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = os.path.abspath(args[0]) if args else os.getcwd()
    families = None
    if '--family' in sys.argv:
        families = set(sys.argv[sys.argv.index('--family') + 1].split(','))
    findings, meta = run(root, families)
    if '--json' in sys.argv:
        print(json.dumps({'findings': findings, 'meta': meta,
                          'not_enforced': NOT_ENFORCED}, ensure_ascii=False, indent=2))
    else:
        n = {s: len([f for f in findings if f['severity'] == s])
             for s in (BLOCKER, GATE, WARN)}
        print('classes %d   cards %d   BLOCKER %d   GATE %d   WARN %d'
              % (meta['classes'], meta['cards'], n[BLOCKER], n[GATE], n[WARN]))
        for sev in (BLOCKER, GATE, WARN):
            for f in [x for x in findings if x['severity'] == sev][:40]:
                print('  %-8s %-6s %s  %s' % (sev, f['id'], f['where'], f['message']))
        print('\nnot enforced, declared in the open:')
        for aid, what, why in NOT_ENFORCED:
            print('  %-6s %s (%s)' % (aid, what, why))
    return 1 if any(f['severity'] == BLOCKER for f in findings) else 0


if __name__ == '__main__':
    sys.exit(main())
