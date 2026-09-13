# -*- coding: utf-8 -*-
"""Build `dashboard.html`: a file explorer and a few honest counts, in one openable file.

    py _system/scripts/gen_dashboard.py <vault-root> [--stdout]

Self-contained by necessity, not preference. Browsers block `fetch()` against `file://`,
so a dashboard that loads its index over the wire only works behind a web server, and a
dashboard that needs a web server is one nobody opens. The index is therefore embedded at
generation time, and the file is regenerated rather than refreshed.

Deliberately thin. A tree, a filter, counts by type, and the bond's headline numbers.
Panels get added when the vault has produced something worth a panel. A dashboard built
before there is anything to show is the failure this package names as its own.
"""
import io
import json
import os
import re
import sys

# The shared argument reader, beside this file in `_system/scripts/`. Imported by path rather
# than by package, because these scripts are copied into a vault and run standalone.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _args                                                        # noqa: E402
import _pagestamp                                                   # noqa: E402

USAGE = '''\
usage: gen_dashboard.py [<vault>] [--stdout]
  write dashboard.html. A generator: it owns that file completely'''


SKIP_DIRS = {'.obsidian', '.trash', '.git', 'node_modules', '.claude', '__pycache__'}
CONTENT_EXT = {'.md', '.base', '.canvas'}
# The stamp this page carries. `_pagestamp` is the one place that knows how to fill it in
# and how to read it back. It was declared here as `STAMP` and never used: what reached the
# file was a bare digest nothing could find, over a document hashed with a placeholder in it
# that only this script could reproduce. `GAP-016`.
GENERATOR = 'gen_dashboard'


def _split_fm(text):
    if not text.startswith('---'):
        return None
    nl = text.find('\n')
    if nl == -1 or text[3:nl].strip():
        return None
    end = text.find('\n---', nl)
    return text[nl + 1:end] if end != -1 else None


def _field(fm, key):
    if not fm:
        return None
    m = re.search(r'^%s:\s*(.+?)\s*$' % re.escape(key), fm, re.M)
    return m.group(1).strip('"\'') if m else None


def scan(root):
    """-> (files, counts). One pass, frontmatter read only from the first 2 KB."""
    files, counts = [], {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in CONTENT_EXT:
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            ntype = title = status = None
            try:
                with io.open(path, encoding='utf-8') as fh:
                    head = fh.read(2048)
                fm = _split_fm(head)
                ntype = _field(fm, 'type')
                title = _field(fm, 'title')
                status = _field(fm, 'status')
            except (OSError, UnicodeDecodeError):
                pass
            ntype = ntype or ('base' if ext == '.base' else 'untyped')
            counts[ntype] = counts.get(ntype, 0) + 1
            files.append({'p': rel, 'n': name, 't': ntype,
                          'ti': title or '', 's': status or ''})
    return files, counts


def bond(root):
    p = os.path.join(root, '_system', 'os', 'vault.md')
    out = {}
    try:
        with io.open(p, encoding='utf-8') as fh:
            fm = _split_fm(fh.read(4096))
        for k in ('solai-package', 'solai-archetype', 'solai-tier', 'first-artefact',
                  'output-language'):
            out[k] = _field(fm, k) or ''
    except OSError:
        pass
    return out


HTML = u"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__NAME__</title>
<style>
:root{--bg:#fbfbfa;--fg:#26241f;--dim:#6b675e;--line:#e3e0d8;--card:#fff;--accent:#7a5c3e}
@media(prefers-color-scheme:dark){:root{--bg:#1a1917;--fg:#e8e5de;--dim:#928d82;--line:#302e2a;--card:#211f1c;--accent:#c9a227}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:22px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--dim);font-size:13px;margin-bottom:24px}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;
 padding:10px 14px;min-width:104px}
.stat b{display:block;font-size:21px;font-weight:600;font-variant-numeric:tabular-nums}
.stat span{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.promise{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
 border-radius:6px;padding:12px 16px;margin-bottom:24px;font-size:14px}
.promise span{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em;
 display:block;margin-bottom:2px}
input{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:6px;
 background:var(--card);color:var(--fg);font:inherit;font-size:14px;margin-bottom:6px}
.hint{color:var(--dim);font-size:12px;margin-bottom:18px}
details{border-bottom:1px solid var(--line)}
summary{cursor:pointer;padding:7px 2px;font-weight:500;list-style:none;display:flex;
 justify-content:space-between;align-items:center}
summary::-webkit-details-marker{display:none}
summary::before{content:"›";display:inline-block;margin-right:8px;color:var(--dim);
 transition:transform .12s}
details[open]>summary::before{transform:rotate(90deg)}
summary b{flex:1;font-weight:500}
.n{color:var(--dim);font-size:12px;font-variant-numeric:tabular-nums}
ul{list-style:none;margin:0 0 8px;padding:0 0 0 22px}
li{display:flex;gap:8px;align-items:baseline;padding:3px 0;font-size:14px}
li a{color:var(--fg);text-decoration:none;border-bottom:1px solid transparent}
li a:hover{border-bottom-color:var(--accent)}
.tag{font-size:10px;color:var(--dim);border:1px solid var(--line);border-radius:3px;
 padding:0 5px;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.st{font-size:11px;color:var(--accent)}
footer{margin-top:40px;color:var(--dim);font-size:12px;border-top:1px solid var(--line);
 padding-top:14px}
.empty{color:var(--dim);padding:24px 2px}
</style></head><body><div class="wrap">
<h1>__NAME__</h1>
<div class="sub">__SUB__</div>
__PROMISE__
<div class="row" id="stats"></div>
<input id="q" placeholder="Filter by name, folder, type or status" autocomplete="off">
<div class="hint">Click a file to open it in Obsidian. __COUNTHINT__</div>
<div id="tree"></div>
<footer>Generated by <code>place</code> from the vault as it stood. Regenerate with
<code>py _system/scripts/gen_dashboard.py .</code></footer>
__STAMPLINE__
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
var D=JSON.parse(document.getElementById('data').textContent);
var VAULT=encodeURIComponent(D.vault);
function groups(files){var g={};files.forEach(function(f){
  var i=f.p.lastIndexOf('/');var d=i<0?'(root)':f.p.slice(0,i);(g[d]=g[d]||[]).push(f);});return g;}
function render(filter){
  var q=(filter||'').toLowerCase();
  var files=D.files.filter(function(f){return !q||
    (f.p+' '+f.t+' '+f.s+' '+f.ti).toLowerCase().indexOf(q)>=0;});
  var g=groups(files),keys=Object.keys(g).sort(),out='';
  if(!keys.length){document.getElementById('tree').innerHTML=
    '<div class="empty">Nothing matches that.</div>';return;}
  keys.forEach(function(d){
    var open=(q||keys.length<=8)?' open':'';
    out+='<details'+open+'><summary><b>'+esc(d)+'</b><span class="n">'+g[d].length+'</span></summary><ul>';
    g[d].forEach(function(f){
      var uri='obsidian://open?vault='+VAULT+'&file='+encodeURIComponent(f.p.replace(/\\.md$/,''));
      out+='<li><a href="'+uri+'">'+esc(f.ti||f.n)+'</a>'+
           '<span class="tag">'+esc(f.t)+'</span>'+
           (f.s?'<span class="st">'+esc(f.s)+'</span>':'')+'</li>';});
    out+='</ul></details>';});
  document.getElementById('tree').innerHTML=out;}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
(function(){var s='';D.stats.forEach(function(x){
  s+='<div class="stat"><b>'+x[1]+'</b><span>'+esc(x[0])+'</span></div>';});
  document.getElementById('stats').innerHTML=s;})();
document.getElementById('q').addEventListener('input',function(e){render(e.target.value);});
render('');
</script></body></html>
"""


def render(root, files, counts, meta):
    name = os.path.basename(os.path.abspath(root))
    content = len(files)
    system = len([f for f in files if f['p'].startswith('_system/')
                  or f['p'].startswith('.claude/') or f['p'] == 'CLAUDE.md'])
    stats = [['files', content], ['folders', len({os.path.dirname(f['p']) for f in files})]]
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1])[:5]:
        stats.append([t, n])
    data = json.dumps({'vault': name, 'files': files, 'stats': stats}, ensure_ascii=False)

    sub = ' &middot; '.join(x for x in [
        meta.get('solai-archetype', ''), meta.get('solai-tier', ''),
        'solai ' + meta.get('solai-package', '') if meta.get('solai-package') else ''] if x)
    promise = ''
    if meta.get('first-artefact'):
        promise = ('<div class="promise"><span>First artefact this vault owes</span>%s</div>'
                   % meta['first-artefact'])
    hint = '%d files carry a type; %d do not.' % (
        content - counts.get('untyped', 0), counts.get('untyped', 0))
    ratio = ('System files %d of %d. This dashboard counts itself on the system side.'
             % (system, content)) if content else ''

    html = (HTML.replace('__NAME__', name)
                .replace('__SUB__', sub or 'no bond file: this vault was not built by place')
                .replace('__PROMISE__', promise)
                .replace('__COUNTHINT__', hint + ' ' + ratio)
                .replace('__DATA__', data)
                .replace('__STAMPLINE__', _pagestamp.STAMP % (GENERATOR, '')))
    # Signed LAST, and nothing touches the document afterwards. The first draft of this fix put
    # the digest in the footer as well, for a human to read, and filled that in after signing:
    # the document then differed from the one that was hashed, by the digest itself. One fact,
    # one place. The footer says how to regenerate; the stamp says what was generated.
    return _pagestamp.sign(html, GENERATOR)


def main():
    root, opts, done = _args.parse(sys.argv[1:], USAGE, flags=('--stdout',), values=())
    if done:
        print(done[1])
        return done[0]
    files, counts = scan(root)
    html = render(root, files, counts, bond(root))
    if opts['--stdout']:
        sys.stdout.reconfigure(encoding='utf-8')
        print(html)
        return 0
    out = os.path.join(root, 'dashboard.html')
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    print('dashboard.html  %d files, %d types' % (len(files), len(counts)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
