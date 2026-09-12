#!/usr/bin/env python3
"""Generate a browsable registry from a built knowledge base.

    py kb_site.py <kb-folder> [--type ird] [--out site]

One self-contained HTML file: search, filters, and every clause with a citation
you can copy. It reads only `kb/`, embeds what it needs, and opens from the disk
with no server. That is deliberate. These are internal regulations, and the answer
to where they may live was "the laptop for now", so the registry is a file rather
than a site.

What it can filter on is only what the documents actually carry. Where a facet is
missing from the corpus it is missing here too, and the page says which ones and
why rather than showing an empty control.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# The shared wikilink pattern, from `runtime/`. Imported by path rather than by package:
# these scripts live in the package and are never copied into a vault, so unlike the
# scripts a vault runs there is no copy of it beside them.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
import _wikilink                                                    # noqa: E402

# The kind of document is not a field anywhere in the vault. It is the first word
# of its own title, which is how the documents name themselves, so it is derived
# here and labelled as derived on the page.
KINDS = ['Правила', 'Положение', 'Инструкция', 'Закон', 'Порядок', 'Методика',
         'Регламент', 'Устав', 'Стандарт', 'Приказ']


def frontmatter(text: str) -> dict:
    if not text.startswith('---'):
        return {}
    end = text.find('\n---', 3)
    if end < 0:
        return {}
    fm, key = {}, None
    for raw in text[3:end].splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith(('  - ', '- ')):
            if key:
                fm.setdefault(key, [])
                if isinstance(fm[key], list):
                    fm[key].append(line.split('- ', 1)[1].strip().strip('"\''))
            continue
        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        key, v = k.strip(), v.strip().strip('"\'')
        if v in ('', '[]'):
            fm[key] = []
            key = key if v == '' else None
        elif v.startswith('['):
            fm[key] = [p.strip().strip('"\'') for p in v.strip('[]').split(',') if p.strip()]
            key = None
        else:
            fm[key] = v
            key = None
    return fm


def targets(v) -> list[str]:
    return _wikilink.targets(v)


def derive_kind(title: str) -> str:
    head = title.strip().strip('«"').split()
    if head:
        for k in KINDS:
            if head[0].lower().startswith(k.lower()[:6]):
                return k
    return 'Иное'


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description='Generate the registry page.')
    ap.add_argument('kb')
    ap.add_argument('--type', default='ird')
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    root = Path(args.kb).resolve()
    kb = root / 'kb' if (root / 'kb' / 'records.jsonl').exists() else root
    if not (kb / 'records.jsonl').exists():
        print('no records at %s' % kb)
        return 1
    out_dir = Path(args.out).resolve() if args.out else root / 'site'
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((kb / 'manifest.json').read_text('utf-8'))
    clauses = defaultdict(list)
    with (kb / 'records.jsonl').open(encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            if r['doc_type'] == args.type:
                clauses[r['parent']].append(r)

    docs = []
    for doc_id in sorted(clauses, key=lambda x: (len(x), x)):
        src = kb / 'docs' / ('%s.md' % doc_id)
        fm = frontmatter(src.read_text('utf-8')) if src.exists() else {}
        title = str(fm.get('title') or doc_id)
        signed = str(fm.get('signed') or '')[:10]
        items = sorted(clauses[doc_id], key=lambda r: (r.get('section') or '', r['id']))
        docs.append({
            'id': doc_id,
            'title': title,
            'kind': derive_kind(title),
            'signed': signed,
            'year': signed[:4],
            'streams': targets(fm.get('stream', [])),
            'tags': [t for t in (fm.get('tags') or []) if t],
            'amendments': targets(fm.get('amendments', [])),
            'superseded_by': (targets(fm.get('superseded-by', [])) or [''])[0],
            'path': items[0]['path'] if items else '',
            'clauses': [{
                'id': c['id'],
                'n': c.get('clause') or '',
                'sec': c.get('section') or '',
                'cite': c['cite'],
                'link': c.get('link') or '',
                'text': c['text'],
                'tok': c['tokens'],
            } for c in items],
        })

    data = {
        'name': manifest.get('vault', '').split('\\')[-1],
        'built': manifest.get('built', '')[:10],
        'corpus': manifest.get('corpus', ''),
        'docs': docs,
        'documents': len(docs),
        'clauses': sum(len(d['clauses']) for d in docs),
        'anchors': sum(1 for d in docs for c in d['clauses'] if c['link']),
    }

    page = TEMPLATE.replace('/*__DATA__*/', json.dumps(data, ensure_ascii=False))
    page = page.replace('__GENERATED__', html.escape(date.today().isoformat()))
    target = out_dir / 'index.html'
    target.write_text(page, encoding='utf-8', newline='\n')

    mb = target.stat().st_size / 1_000_000
    print('Registry   %d documents, %d clauses, %d with a deep link'
          % (data['documents'], data['clauses'], data['anchors']))
    print('  %s   %.1f MB' % (target, mb))
    print('  open it from the disk. Nothing is served and nothing leaves the machine.')
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Реестр ВНД</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  color-scheme:dark;
  --bg:#14161a; --panel:#1a1d22; --sunk:#1f232a; --ink:#eceae5; --ink-2:#c2c1ba;
  --muted:#8b8e8b; --line:#2b2f36; --line-2:#3a3f48;
  --accent:#e0b46c; --accent-soft:#251f15; --accent-ink:#1a1408;
  --ok:#71b58c; --warn:#d98a3e; --refuse:#e8756a;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  --r:6px; --r-sm:4px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14.5px/1.6 "IBM Plex Sans",ui-sans-serif,system-ui,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
header{padding:16px 22px;border-bottom:1px solid var(--line);background:var(--panel);
  display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;position:sticky;top:0;z-index:5}
header h1{margin:0;font-family:var(--mono);font-size:17px;font-weight:500;letter-spacing:-.02em}
header .counts{font:11.5px/1 var(--mono);color:var(--muted);margin-left:auto}
header .counts b{color:var(--ink-2);font-weight:500}

.bar{display:flex;gap:8px;padding:12px 22px;border-bottom:1px solid var(--line);
  flex-wrap:wrap;align-items:center;background:var(--bg);position:sticky;top:53px;z-index:4}
input,select{font:13px/1 inherit;color:var(--ink);background:var(--sunk);
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:9px 11px}
input:focus,select:focus{outline:none;border-color:var(--accent)}
input[type=search]{flex:1 1 300px;min-width:180px;font-family:var(--mono)}
button.clear{font:12px/1 inherit;color:var(--muted);background:transparent;
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:9px 12px;cursor:pointer}
button.clear:hover{color:var(--accent);border-color:var(--accent)}
.hint{font:11.5px/1 var(--mono);color:var(--muted)}

main{display:grid;grid-template-columns:340px minmax(0,1fr);gap:0;align-items:start}
@media (max-width:900px){main{grid-template-columns:minmax(0,1fr)}}
.list{border-right:1px solid var(--line);max-height:calc(100vh - 106px);overflow:auto}
@media (max-width:900px){.list{max-height:none;border-right:0;border-bottom:1px solid var(--line)}}
.doc{padding:12px 18px;border-bottom:1px solid var(--line);cursor:pointer}
.doc:hover{background:var(--sunk)}
.doc.on{background:var(--accent-soft);box-shadow:inset 3px 0 0 var(--accent)}
.doc .id{font:500 12px/1 var(--mono);color:var(--accent)}
.doc .t{font-size:13px;margin:5px 0 6px;color:var(--ink-2);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.doc .m{font:10.5px/1.5 var(--mono);color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}
.pane{padding:22px 26px 60px;min-width:0}
.pane h2{margin:0 0 6px;font-family:var(--mono);font-size:16px;font-weight:500;
  letter-spacing:-.02em;line-height:1.35}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 20px}
.pill{font:10.5px/1 var(--mono);border:1px solid var(--line-2);border-radius:99px;
  padding:6px 9px;color:var(--muted)}
.pill.k{border-color:var(--accent);color:var(--accent)}
.pill.no{border-color:var(--refuse);color:var(--refuse)}
.cl{border-top:1px solid var(--line);padding:13px 0}
.cl:last-child{border-bottom:1px solid var(--line)}
.cl .h{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.cl .n{font:500 12px/1.5 var(--mono);color:var(--accent);white-space:nowrap}
.cl .s{font:11px/1.5 var(--mono);color:var(--muted)}
.cl .cp{margin-left:auto;font:10.5px/1 var(--mono);color:var(--muted);background:transparent;
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:5px 8px;cursor:pointer}
.cl .cp:hover{color:var(--accent);border-color:var(--accent)}
.cl .body{margin:8px 0 0;font-size:13.5px;color:var(--ink-2)}
.cl .body p{margin:0 0 8px;white-space:pre-wrap}
.cl .body p:last-child{margin-bottom:0}
.cl .body ul{margin:4px 0 8px;padding-left:20px}
.cl .body li{margin-bottom:4px}
.cl .body b{color:var(--ink)}
.tw{overflow-x:auto;margin:8px 0;border:1px solid var(--line);border-radius:var(--r-sm)}
.cl .body table{border-collapse:collapse;width:100%;min-width:420px;font-size:12.5px}
.cl .body th{text-align:left;padding:8px 11px;background:var(--sunk);color:var(--muted);
  font:600 10.5px/1.4 var(--mono);letter-spacing:.04em;text-transform:uppercase;
  border-bottom:1px solid var(--line);vertical-align:top}
.cl .body td{padding:8px 11px;border-bottom:1px solid var(--line);vertical-align:top;
  color:var(--ink-2)}
.cl .body tr:last-child td{border-bottom:0}
.cl mark{background:var(--accent-soft);color:var(--accent);border-radius:2px;padding:0 2px}
.empty{color:var(--muted);font-size:13.5px;padding:20px 0}
.limits{margin:34px 0 0;padding:16px 18px;border:1px dashed var(--line-2);border-radius:var(--r);
  background:var(--sunk)}
.limits b{display:block;font-size:13.5px;margin-bottom:8px;color:var(--ink)}
.limits li{font-size:12.5px;color:var(--muted);margin-bottom:6px;line-height:1.5}
.limits ul{margin:0;padding-left:18px}
.hitdoc{font:500 12px/1 var(--mono);color:var(--accent);margin:22px 0 2px}
.hitdoc:first-child{margin-top:0}
.more{font:11px/1 var(--mono);color:var(--muted);background:transparent;cursor:pointer;
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:4px 8px;margin-left:4px}
.more:hover{color:var(--accent);border-color:var(--accent)}
.more.page{display:block;margin:16px 0 0;padding:9px 14px;font-size:12px}
.body.snip{color:var(--muted)}
.byname{font:11px/1.5 var(--mono);color:var(--muted);margin:2px 0 6px}

/* filters as chips: what the corpus holds, visible without opening a control */
.filters{padding:10px 22px 14px;border-bottom:1px solid var(--line);background:var(--bg);
  display:flex;flex-direction:column;gap:7px}
.fgroup{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.flabel{font:10.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);width:52px;flex:0 0 52px}
.chip{font:11.5px/1 inherit;color:var(--ink-2);background:var(--sunk);cursor:pointer;
  border:1px solid var(--line);border-radius:99px;padding:6px 10px;display:inline-flex;
  gap:6px;align-items:baseline}
.chip i{font-style:normal;font:10.5px/1 var(--mono);color:var(--muted)}
.chip:hover{border-color:var(--line-2);color:var(--ink)}
.chip.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent)}
.chip.on i{color:var(--accent)}
.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
</style>
</head>
<body>

<header>
  <h1>Реестр ВНД</h1>
  <span class="hint" id="sub"></span>
  <span class="counts" id="counts"></span>
</header>

<div class="bar">
  <input type="search" id="q" placeholder="поиск по названию документа и по тексту пунктов…" autocomplete="off">
  <button class="clear" id="clear">сбросить</button>
  <span class="hint" id="found"></span>
</div>
<div class="filters" id="filters"></div>

<main>
  <div class="list" id="list"></div>
  <div class="pane" id="pane"></div>
</main>

<script>
const DATA = /*__DATA__*/;
const $ = s => document.querySelector(s);
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const rx = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const MIN_Q = 2;      // one letter matches everything, which is not a search
const MAX_HITS = 80;  // a screen of results, not a corpus dump
const PAGE = 15;      // clauses laid out at once. Tables are expensive to lay out

// Lowercase once, at load. Doing it per keystroke meant re-reading the whole
// corpus for every letter typed.
DATA.docs.forEach(d => {
  d.lc = (d.id + ' ' + d.title).toLowerCase();
  d.clauses.forEach(c => { c.lc = c.text.toLowerCase(); });
});

// Russian declines and the index does not, so a long word matches by its prefix.
function stems(q){
  return (q.toLowerCase().match(/[0-9a-zа-яё_-]{2,}/gi) || [])
    .map(w => w.length >= 6 ? w.slice(0, -3) : w);
}
const hasAll = (lc, st) => st.every(s => lc.includes(s));

function highlight(escaped, st){
  let out = escaped;
  st.forEach(s => {
    if (s.length < 3) return;
    out = out.replace(new RegExp('(' + rx(s) + '[а-яё]*)', 'gi'), '<mark>$1</mark>');
  });
  return out;
}

function snippet(c, st){
  let at = -1;
  st.forEach(s => { const i = c.lc.indexOf(s); if (i >= 0 && (at < 0 || i < at)) at = i; });
  const from = Math.max(0, at - 90);
  const cut = c.text.slice(from, from + 300);
  return (from ? '…' : '') + highlight(esc(cut), st) + (from + 300 < c.text.length ? '…' : '');
}

function inline(t){
  return t.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
          .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>');
}

// A clause body is markdown and 96 of them are tables. Escape, then highlight,
// then structure, so the marks survive into the cells.
function mdToHtml(src, st){
  let text = esc(src);
  if (st && st.length) text = highlight(text, st);
  const lines = text.split('\n'), out = [];
  const isRow = l => /^\s*\|.*\|\s*$/.test(l);
  const cells = l => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
  let i = 0;
  while (i < lines.length){
    if (isRow(lines[i]) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i+1])){
      const head = cells(lines[i]); i += 2; const rows = [];
      while (i < lines.length && isRow(lines[i])){ rows.push(cells(lines[i])); i++; }
      out.push('<div class="tw"><table><thead><tr>' +
        head.map(h => '<th>' + inline(h) + '</th>').join('') + '</tr></thead><tbody>' +
        rows.map(r => '<tr>' + r.map(c => '<td>' + inline(c) + '</td>').join('') + '</tr>').join('') +
        '</tbody></table></div>');
      continue;
    }
    if (/^\s*[-*]\s+/.test(lines[i])){
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])){
        items.push('<li>' + inline(lines[i].replace(/^\s*[-*]\s+/, '')) + '</li>'); i++;
      }
      out.push('<ul>' + items.join('') + '</ul>');
      continue;
    }
    const para = [];
    while (i < lines.length && !isRow(lines[i]) && !/^\s*[-*]\s+/.test(lines[i])){
      para.push(lines[i]); i++;
    }
    const body = para.join('\n').trim();
    if (body) out.push('<p>' + inline(body) + '</p>');
  }
  return out.join('');
}

const F = {kind:'', year:'', stream:''};
let sel = DATA.docs.length ? DATA.docs[0].id : null;
let shown = PAGE;

function tally(pick){
  const m = new Map();
  DATA.docs.forEach(d => pick(d).forEach(v => v && m.set(v, (m.get(v) || 0) + 1)));
  return [...m.entries()];
}
const GROUPS = [
  {key:'kind',   label:'вид',   items: tally(d => [d.kind]).sort((a,b) => b[1]-a[1])},
  {key:'year',   label:'год',   items: tally(d => [d.year]).sort((a,b) => b[0].localeCompare(a[0]))},
  {key:'stream', label:'поток', items: tally(d => d.streams).sort((a,b) => b[1]-a[1])},
];

function renderChips(){
  $('#filters').innerHTML = GROUPS.filter(g => g.items.length).map(g =>
    '<div class="fgroup"><span class="flabel">' + g.label + '</span>' +
    g.items.map(([v, n]) =>
      '<button class="chip' + (F[g.key] === v ? ' on' : '') + '" data-k="' + g.key +
      '" data-v="' + esc(v) + '">' + esc(v) + ' <i>' + n + '</i></button>').join('') +
    '</div>').join('');
  document.querySelectorAll('.chip').forEach(b => b.onclick = () => {
    F[b.dataset.k] = (F[b.dataset.k] === b.dataset.v) ? '' : b.dataset.v;
    // Keep the open document if it still matches. Otherwise show the list rather
    // than rendering whichever document sorts first: that is how a single chip
    // click ended up laying out 460 clauses of IRD-007.
    if (!filtered().some(d => d.id === sel)) sel = null;
    shown = PAGE;
    renderChips();
    render();
  });
}

function filtered(){
  return DATA.docs.filter(d =>
    (!F.kind || d.kind === F.kind) && (!F.year || d.year === F.year) &&
    (!F.stream || d.streams.includes(F.stream)));
}

function query(){
  const q = $('#q').value.trim();
  return q.length >= MIN_Q ? stems(q) : [];
}

function render(){
  const st = query();
  const docs = filtered();

  $('#list').innerHTML = docs.map(d => {
    const n = st.length
      ? (hasAll(d.lc, st) ? 1 : 0) + d.clauses.filter(c => hasAll(c.lc, st)).length : 0;
    return '<div class="doc' + (d.id === sel ? ' on' : '') + '" data-id="' + d.id + '">' +
      '<div class="id">' + d.id + (st.length ? ' &middot; ' + n + ' совп.' : '') + '</div>' +
      '<div class="t">' + esc(d.title) + '</div>' +
      '<div class="m"><span>' + esc(d.kind) + '</span><span>' + (d.signed || 'дата ?') +
      '</span><span>' + d.clauses.length + ' п.</span></div></div>';
  }).join('') || '<div class="empty" style="padding:20px 18px">Ничего не найдено.</div>';

  document.querySelectorAll('.doc').forEach(el =>
    el.onclick = () => { sel = el.dataset.id; shown = PAGE; $('#q').value = ''; render(); });

  if (st.length) renderSearch(docs, st); else renderDoc();
}

function head(c){
  return '<div class="h"><span class="n">' + (c.n ? 'п. ' + c.n : '—') + '</span>' +
    (c.sec ? '<span class="s">' + esc(c.sec) + '</span>' : '') +
    '<button class="cp" data-cite="' + esc(c.cite) + '">копировать ссылку</button></div>';
}

function renderSearch(docs, st){
  let n = 0, total = 0, out = '';
  docs.forEach(d => {
    const hits = d.clauses.filter(c => hasAll(c.lc, st));
    const byName = hasAll(d.lc, st);
    total += hits.length;
    if (!hits.length && !byName) return;
    if (n >= MAX_HITS) return;
    out += '<div class="hitdoc">' + d.id + ' &middot; ' + esc(d.title) + '</div>';
    if (byName && !hits.length){
      out += '<div class="byname">совпадение в названии документа</div>';
      return;
    }
    if (byName) out += '<div class="byname">название документа тоже совпадает</div>';
    hits.forEach(c => {
      if (n >= MAX_HITS) return;
      n++;
      out += '<div class="cl" data-id="' + esc(c.id) + '">' + head(c) +
        '<div class="body snip">' + snippet(c, st) +
        ' <button class="more" data-id="' + esc(c.id) + '">пункт целиком</button></div></div>';
    });
  });
  $('#found').textContent = total
    ? (total + ' совпадений' + (total > n ? ', показаны первые ' + n : ''))
    : 'нет совпадений: это тоже ответ';
  $('#pane').innerHTML = out ||
    '<div class="empty">Ни один пункт не содержит всех слов запроса. ' +
    'Корпус не отвечает на этот вопрос.</div>';
  wire(st);
}

function renderDoc(){
  $('#found').textContent = '';
  const d = DATA.docs.find(x => x.id === sel);
  if (!d){
    const n = filtered().length;
    $('#pane').innerHTML = '<div class="empty">' + (n
      ? 'Документов по фильтру: ' + n + '. Выберите один в списке слева.'
      : 'Под эти фильтры не подходит ни один документ.') + '</div>';
    return;
  }
  const pills = ['<span class="pill k">' + esc(d.kind) + ' (выведено из названия)</span>',
    '<span class="pill">подписан ' + (d.signed || '—') + '</span>',
    '<span class="pill">' + d.clauses.length + ' пунктов</span>']
    .concat(d.streams.map(x => '<span class="pill">' + esc(x) + '</span>'))
    .concat(d.tags.map(t => '<span class="pill">' + esc(t) + '</span>'))
    .concat(d.amendments.map(a => '<span class="pill">поправка ' + esc(a) + '</span>'))
    .concat(d.superseded_by ? ['<span class="pill no">отменён: ' + esc(d.superseded_by) + '</span>'] : []);

  const slice = d.clauses.slice(0, shown);
  const rest = d.clauses.length - slice.length;
  $('#pane').innerHTML = '<h2>' + d.id + ' &middot; ' + esc(d.title) + '</h2>' +
    '<div class="meta">' + pills.join('') + '</div>' +
    slice.map(c => '<div class="cl">' + head(c) +
      '<div class="body">' + mdToHtml(c.text, null) + '</div></div>').join('') +
    (rest > 0 ? '<button class="more page" id="page">показать ещё ' +
       Math.min(rest, PAGE) + ' из ' + rest + '</button>' : '') +
    '<div class="limits"><b>Чего этот реестр не знает</b><ul>' +
    '<li>Действует ли документ. Во всём корпусе один признак отмены, поэтому фильтра «действующие» нет.</li>' +
    '<li>Дату вступления в силу и срок действия. Есть только дата подписания.</li>' +
    '<li>Кем утверждён и каким приказом. Поля нет ни в одном документе.</li>' +
    '<li>Связи между ВНД: ссылки есть в тексте пунктов, но не как данные.</li>' +
    '</ul></div>';
  const pg = $('#page');
  if (pg) pg.onclick = () => { shown += PAGE; renderDoc(); };
  wire(null);
}

function wire(st){
  document.querySelectorAll('.cp').forEach(b => b.onclick = () => {
    const t = b.dataset.cite;
    navigator.clipboard?.writeText(t).then(
      () => { b.textContent = 'скопировано';
              setTimeout(() => b.textContent = 'копировать ссылку', 1400); },
      () => { b.textContent = t; });
  });
  // Full markdown is built for one clause at a time, when asked. Building it for
  // every hit is what made typing feel like a hang.
  document.querySelectorAll('.more[data-id]').forEach(b => b.onclick = () => {
    const id = b.dataset.id;
    let found = null;
    DATA.docs.forEach(d => d.clauses.forEach(c => { if (c.id === id) found = c; }));
    if (!found) return;
    b.closest('.body').outerHTML = '<div class="body">' + mdToHtml(found.text, st) + '</div>';
    wire(st);
  });
}

// A blank page tells you nothing. If something throws, say what and where.
window.onerror = (msg, src, line, col) => {
  const bar = $('#found');
  if (bar) bar.textContent = 'ошибка: ' + msg + ' (строка ' + line + ':' + col + ')';
  return false;
};

let timer = 0;
$('#q').addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(render, 150);
});
$('#clear').onclick = () => {
  $('#q').value = ''; F.kind = ''; F.year = ''; F.stream = '';
  sel = (DATA.docs[0] || {}).id; shown = PAGE;
  renderChips(); render();
};

$('#counts').innerHTML = '<b>' + DATA.documents + '</b> документов &middot; <b>' +
  DATA.clauses + '</b> пунктов &middot; сборка ' + DATA.built;
$('#sub').textContent = 'корпус ' + DATA.corpus;
renderChips();
render();
</script>
</body>
</html>
"""


if __name__ == '__main__':
    sys.exit(main())
