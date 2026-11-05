"""Детективная доска: разбор сцены в виде одной HTML-страницы.

Доска показывает цепочку «предмет или след → улика → утверждение → версия»
нитями, рядом — полный список находок с оговорками, источниками и
опровержениями, и отдельно — следы, под которые не подошло ни одно правило.

Страница самодостаточна: один файл, без сети, без внешних ресурсов.

Правка страницы не меняет разбор. Она показывает разбор и собирает команду
переразбора; истина остаётся в движке.
"""

import html
import json

from .paths import PathError, resolve


def implicit_anchors(scene, rule):
    """Объекты, на которых сработало правило, если в правиле нет явных якорей.

    Предикат правила — это запрос к сцене, поэтому по нему видно, что именно
    вызвало срабатывание. Это не новый якорь улики: в `anchors` правила его
    по-прежнему нет, и доска показывает это как «неявный».
    """
    path = (rule.predicate or {}).get("path") if rule else None
    if not path:
        return []
    try:
        items = resolve(scene, path)
    except PathError:
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]

CSS = """
:root{
  --cork-1:#3c2b1d; --cork-2:#201510; --paper:#f0e5cb; --paper-2:#e0d0ae;
  --paper-3:#f7efdc; --ink:#2a2017; --ink-soft:#6a5947; --rule:#8d7a60;
  --red:#c0392b; --gold:#d9a72c; --steel:#6f93b8; --green:#5f7a3c; --violet:#8b6bb1;
  --shadow:0 12px 26px rgba(0,0,0,.45), 0 2px 4px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:linear-gradient(170deg,#171009,#241710 60%,#120c07);
  color:var(--ink);font:15px/1.55 "Segoe UI",Roboto,system-ui,sans-serif;
}
h1,h2,h3{font-family:Georgia,"Times New Roman",serif;font-weight:600;margin:0}
a{color:#7c5b2a}
.wrap{max-width:1680px;margin:0 auto;padding:0 22px 70px}

.masthead{position:relative;padding:26px 4px 18px;border-bottom:1px solid rgba(255,225,180,.14)}
.masthead .kicker{letter-spacing:.32em;text-transform:uppercase;font-size:11px;color:#c9a86a}
.masthead h1{color:#f6e6c8;font-size:34px;letter-spacing:.01em;margin:8px 0 6px}
.masthead .sub{color:#b7a48a;max-width:90ch;font-size:14px}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.badge{
  display:inline-flex;align-items:center;gap:7px;padding:5px 12px;border-radius:999px;
  font-size:12px;letter-spacing:.04em;border:1px solid rgba(255,225,180,.22);
  background:rgba(255,220,170,.07);color:#e8d5b3;
}
.badge b{color:#fff5e2;font-weight:600}
.badge.warn{border-color:rgba(217,167,44,.55);background:rgba(217,167,44,.13);color:#f0d493}
.badge.good{border-color:rgba(95,122,60,.7);background:rgba(95,122,60,.18);color:#cfe0b4}

.tabs{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 0}
.tab{
  cursor:pointer;padding:9px 16px;border-radius:8px 8px 0 0;font-size:14px;
  border:1px solid rgba(255,225,180,.14);border-bottom:none;color:#c3ae8d;background:rgba(255,255,255,.03);
}
.tab.on{background:var(--paper);color:var(--ink);font-weight:600;box-shadow:0 -6px 18px rgba(0,0,0,.35)}
.panel{display:none;padding-top:18px}
.panel.on{display:block}

.board{
  position:relative;border-radius:14px;padding:26px 22px 30px;overflow:hidden;
  border:1px solid rgba(255,225,180,.12);box-shadow:var(--shadow);
  background:
    radial-gradient(1100px 620px at 18% -10%, rgba(255,205,140,.12), transparent 62%),
    radial-gradient(900px 620px at 92% 110%, rgba(0,0,0,.42), transparent 60%),
    repeating-linear-gradient(115deg, rgba(255,255,255,.022) 0 2px, rgba(0,0,0,.03) 2px 5px),
    linear-gradient(160deg,var(--cork-1),var(--cork-2));
}
.cols{position:relative;display:grid;grid-template-columns:1.05fr 1.15fr 1.15fr .95fr;gap:96px;z-index:2}
.col h3{
  color:#e9d4ac;font-size:12px;letter-spacing:.22em;text-transform:uppercase;
  margin:0 0 12px;padding-bottom:8px;border-bottom:1px dashed rgba(233,212,172,.28)
}
.col .stack{display:flex;flex-direction:column;gap:16px}
.strings{position:absolute;inset:0;width:100%;height:100%;z-index:5;pointer-events:none;overflow:visible}
.strings path{fill:none;stroke-linecap:round;filter:drop-shadow(0 2px 2px rgba(0,0,0,.55));
  transition:stroke-width .15s,opacity .15s}
.strings path.s-scene{stroke:var(--gold)}
.strings path.s-evid{stroke:var(--red)}
.strings path.s-ver{stroke:var(--steel)}
.strings text{
  font:700 10.5px/1 "Segoe UI",system-ui,sans-serif;letter-spacing:.05em;
  paint-order:stroke;stroke:rgba(20,12,6,.9);stroke-width:4px;stroke-linejoin:round
}
.strings text.s-scene{fill:#f0cf87}
.strings text.s-evid{fill:#f4b1a8}
.strings text.s-ver{fill:#bcd8f0}

.card{
  position:relative;background:linear-gradient(178deg,var(--paper-3),var(--paper));
  border-radius:3px;padding:13px 14px 12px;color:var(--ink);
  box-shadow:var(--shadow);outline:1px solid rgba(120,96,63,.35);outline-offset:-1px}
.card::before{
  content:"";position:absolute;left:13px;top:-7px;width:15px;height:15px;border-radius:50%;
  background:radial-gradient(circle at 34% 30%,#f0c1a0,#a8382c 62%,#5d1a13);
  box-shadow:0 3px 5px rgba(0,0,0,.5);z-index:3
}
.card .kind{
  font:700 10px/1 "Segoe UI",system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase;
  color:var(--ink-soft);display:flex;justify-content:space-between;align-items:center;gap:8px
}
.card h4{font:600 16px/1.3 Georgia,serif;margin:7px 0 6px}
.card .note{font-size:12.5px;color:var(--ink-soft);margin:0 0 7px}
.card .rows{margin:0;font-size:12.5px}
.card .rows div{display:flex;gap:8px;padding:2px 0;border-top:1px dotted rgba(120,96,63,.35)}
.card .rows div:first-child{border-top:none}
.card .rows span:first-child{color:var(--ink-soft);min-width:88px}
.card.gap{background:linear-gradient(178deg,#f4e7e6,#ead7d4);outline-color:rgba(176,57,43,.5)}
.card.gap .kind{color:#9d3b2c}
.card.refuted{filter:saturate(.7)}
.card .flag{
  display:inline-block;padding:1px 7px;border-radius:999px;font-size:10.5px;font-weight:700;
  letter-spacing:.04em;border:1px solid currentColor
}
.card .flag.ok{color:var(--green)}
.card .flag.warn{color:#b8860b}
.card .flag.bad{color:var(--red)}
.card .flag.draft{color:var(--ink-soft)}

.bar{height:7px;border-radius:4px;background:rgba(90,74,55,.18);overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#b6761f,#e3bc63)}
.bar.conf i{background:linear-gradient(90deg,#8d3b2c,#d8735c)}
.bar.logodds i{background:linear-gradient(90deg,#3f6b96,#7fb0d8)}

.panel-h{color:#f2e3c8;font:600 22px/1.2 Georgia,serif;margin:0 0 6px}
.panel-sub{color:#b49f81;font-size:13.5px;margin:0 0 16px;max-width:100ch}

table.grid{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;
  background:var(--paper);border-radius:10px;overflow:hidden;box-shadow:var(--shadow)}
table.grid th{
  text-align:left;padding:10px 12px;background:linear-gradient(180deg,#3b2a1c,#2a1d13);
  color:#e9d4ac;font:600 11px/1.3 "Segoe UI",system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;
  border-bottom:1px solid #191009;position:sticky;top:0
}
table.grid td{padding:9px 12px;border-bottom:1px solid rgba(120,96,63,.22);vertical-align:top}
table.grid tr:last-child td{border-bottom:none}
table.grid tr:nth-child(even) td{background:rgba(120,96,63,.06)}
table.grid td.mono{font-family:"JetBrains Mono",Consolas,monospace;font-size:12px;white-space:nowrap}
table.grid .sub{color:var(--ink-soft);font-size:12px}

.dossier{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.dossier .d{
  background:var(--paper);border-radius:10px;padding:14px 16px;box-shadow:var(--shadow);
  border-left:5px solid var(--red)
}
.dossier .d h4{font:600 16px/1.3 Georgia,serif;margin:0 0 4px}
.dossier .d .meta{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-soft);margin-bottom:9px}
.dossier .d p{margin:0 0 8px;font-size:13px}
.dossier .d ul{margin:0 0 8px;padding-left:18px;font-size:12.5px;color:#4a3c2d}
.dossier .d .src{font-size:12px;color:#5d4c39;border-top:1px dotted rgba(120,96,63,.4);padding-top:7px}

.cols2{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}
.claim{background:var(--paper);border-radius:10px;padding:16px 18px;box-shadow:var(--shadow);position:relative}
.claim .cid{font:700 11px/1 "Segoe UI",system-ui,sans-serif;letter-spacing:.16em;color:var(--ink-soft)}
.claim h4{font:600 17px/1.35 Georgia,serif;margin:7px 0 9px}
.claim .meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:9px;font-size:11.5px}
.claim .meta .chip{padding:2px 9px;border-radius:999px;border:1px solid rgba(120,96,63,.4);color:#5b4a38}
.claim ul{margin:6px 0 0;padding-left:18px;font-size:12.5px;color:#4a3c2d}
.claim .quote{
  margin:10px 0 0;padding:9px 12px;border-left:3px solid var(--gold);
  background:rgba(217,167,44,.1);font-size:12.5px;font-style:italic;color:#4d3f2e
}
.claim .quote b{font-style:normal}
.ver{background:var(--paper);border-radius:10px;padding:16px 18px;box-shadow:var(--shadow);border-top:5px solid var(--steel)}
.ver h4{font:600 17px/1.35 Georgia,serif;margin:4px 0 9px}
.ver .disc{background:rgba(111,147,184,.12);border-left:3px solid var(--steel);padding:9px 12px;font-size:12.5px;margin-top:9px}

.rerun{background:var(--paper);border-radius:10px;padding:18px;box-shadow:var(--shadow)}
.rerun textarea{
  width:100%;height:320px;font-family:"JetBrains Mono",Consolas,monospace;font-size:12.5px;
  border:1px solid rgba(120,96,63,.45);border-radius:8px;padding:12px;background:#fbf6e9;color:#2a2017;resize:vertical
}
.cmd{
  display:flex;gap:10px;align-items:center;justify-content:space-between;
  background:#241a12;color:#e8d5b3;border-radius:8px;padding:9px 12px;margin:9px 0;font-size:12.5px
}
.cmd code{font-family:"JetBrains Mono",Consolas,monospace}
.cmd button{
  cursor:pointer;background:rgba(255,225,180,.12);border:1px solid rgba(255,225,180,.28);color:#f2e3c8;
  border-radius:6px;padding:5px 11px;font-size:12px;white-space:nowrap
}
.cmd button:hover{background:rgba(255,225,180,.22)}
.note-box{border:1px dashed rgba(217,167,44,.55);border-radius:10px;padding:14px 16px;margin:16px 0;
  background:rgba(217,167,44,.08);color:#e9d7b6;font-size:13.5px}
.toolbar{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 14px}
.toolbar button{
  cursor:pointer;border-radius:8px;padding:8px 14px;font-size:13px;
  background:var(--paper);color:var(--ink);border:1px solid rgba(120,96,63,.4);box-shadow:0 2px 6px rgba(0,0,0,.3)
}
.toolbar button:hover{background:var(--paper-3)}
.narrative{background:var(--paper);border-radius:10px;padding:18px 22px;box-shadow:var(--shadow);
  white-space:pre-wrap;font-size:14px;line-height:1.6;max-width:96ch}
.hidden{display:none !important}
@media (max-width:1180px){.cols{grid-template-columns:1fr 1fr}}
"""

JS = """
const LINKS = window.__LINKS__ || [];
const board = document.getElementById('board');
const svg = document.getElementById('strings');

function nodeEl(id){ return document.querySelector('[data-node="'+id+'"]'); }

function draw(){
  if(!svg) return;
  const box = board.getBoundingClientRect();
  svg.setAttribute('viewBox', '0 0 '+box.width+' '+box.height);
  svg.setAttribute('width', box.width);
  svg.setAttribute('height', box.height);
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  const dim = board.classList.contains('dim');
  const gutters = {};
  LINKS.forEach(function(l){
    const a = nodeEl(l.from), b = nodeEl(l.to);
    if(!a || !b) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const x1 = ra.right - box.left, y1 = ra.top - box.top + ra.height/2;
    const x2 = rb.left - box.left,  y2 = rb.top - box.top + rb.height/2;
    const xm = (x1 + x2) / 2;
    const key = Math.round(xm/40);
    gutters[key] = (gutters[key] || 0) + 1;
    const nudge = (gutters[key] - 1) * 13;
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d', 'M '+x1+' '+y1+' C '+(xm-46)+' '+y1+' '+(xm+46)+' '+y2+' '+x2+' '+y2);
    path.setAttribute('class','s-'+l.kind);
    path.setAttribute('stroke-width', l.hot ? 3 : 1.8);
    path.setAttribute('opacity', dim && !l.hot ? 0.12 : 0.9);
    svg.appendChild(path);
    const ly = (y1 + y2) / 2 + nudge;
    const lx = xm;
    const text = document.createElementNS('http://www.w3.org/2000/svg','text');
    text.setAttribute('x', lx); text.setAttribute('y', ly + 3.5);
    text.setAttribute('text-anchor','middle');
    text.setAttribute('class','s-'+l.kind);
    text.setAttribute('opacity', dim && !l.hot ? 0.15 : 1);
    text.textContent = l.label;
    svg.appendChild(text);
    const w = l.label.length * 5.6 + 12;
    const rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
    rect.setAttribute('x', lx - w/2); rect.setAttribute('y', ly - 9);
    rect.setAttribute('width', w); rect.setAttribute('height', 14);
    rect.setAttribute('rx', 4);
    rect.setAttribute('fill','rgba(18,11,5,.82)');
    rect.setAttribute('opacity', dim && !l.hot ? 0.15 : 1);
    svg.insertBefore(rect, text);
  });
}

function focusLink(id){
  const keep = {};
  LINKS.forEach(function(l){
    if(l.from === id || l.to === id){ keep[l.from]=1; keep[l.to]=1; l.hot = true; }
    else { l.hot = false; }
  });
  document.querySelectorAll('[data-node]').forEach(function(n){
    n.classList.toggle('hidden', !(n.dataset.node in keep) && n.dataset.node !== id);
  });
  board.classList.add('dim');
  draw();
}

function resetBoard(){
  LINKS.forEach(function(l){ l.hot = false; });
  document.querySelectorAll('[data-node]').forEach(function(n){ n.classList.remove('hidden'); });
  board.classList.remove('dim');
  draw();
}

function openTab(id){
  document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('on', t.dataset.tab === id); });
  document.querySelectorAll('.panel').forEach(function(p){ p.classList.toggle('on', p.id === id); });
  if(id === 'board') draw();
}

document.querySelectorAll('.tab').forEach(function(tab){
  tab.addEventListener('click', function(){ openTab(tab.dataset.tab); });
});
window.addEventListener('hashchange', function(){ openTab(location.hash.slice(1) || 'board'); });

document.querySelectorAll('[data-node]').forEach(function(n){
  n.addEventListener('click', function(){ focusLink(n.dataset.node); });
});
document.getElementById('reset').addEventListener('click', resetBoard);

function copy(text, btn){
  const done = function(){ const old = btn.textContent; btn.textContent = 'скопировано';
    setTimeout(function(){ btn.textContent = old; }, 1400); };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, function(){ fallback(text); done(); });
  } else { fallback(text); done(); }
}
function fallback(text){
  const ta = document.createElement('textarea');
  ta.value = text; document.body.appendChild(ta); ta.select();
  try{ document.execCommand('copy'); }catch(e){}
  document.body.removeChild(ta);
}
document.querySelectorAll('[data-copy]').forEach(function(btn){
  btn.addEventListener('click', function(){
    const src = document.querySelector(btn.dataset.copy);
    copy(src ? src.value || src.textContent : '', btn);
  });
});
document.getElementById('download').addEventListener('click', function(){
  const ta = document.getElementById('ledger');
  const blob = new Blob([ta.value], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'ledger.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
});

window.addEventListener('resize', draw);
window.addEventListener('load', function(){
  const wanted = location.hash.slice(1);
  if(wanted && document.getElementById(wanted)) openTab(wanted);
  draw();
});
setTimeout(draw, 60);
"""

TAB_BAR = [
    ("board", "Доска"),
    ("facts", "Факты"),
    ("findings", "Находки"),
    ("claims", "Утверждения"),
    ("versions", "Версии"),
    ("rerun", "Переразбор"),
]


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def truncate(text, limit=140):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _element_index(scene):
    index = {}
    for collection in ("objects", "regions", "surfaces"):
        for item in scene.get(collection) or []:
            index[item.get("id")] = (collection, item)
    return index


def _element_label(collection, item):
    if collection == "objects":
        note = item.get("note")
        return f"{item.get('category')}" + (f" — {truncate(note, 110)}" if note else "")
    if collection == "regions":
        note = item.get("note")
        return f"след: {item.get('kind')}" + (f" — {truncate(note, 110)}" if note else "")
    return item.get("name") or collection


def _node(node_id, kind, title, body, extra=""):
    return (
        f'<div class="card {extra}" data-node="{esc(node_id)}">'
        f'<div class="kind"><span>{esc(kind)}</span></div>'
        f'<h4>{esc(title)}</h4>'
        + (f'<p class="note">{esc(body)}</p>' if body else "")
        + "</div>"
    )


def _weight_width(weight):
    if not isinstance(weight, (int, float)):
        return 0
    return int(min(100, abs(weight) / 6.0 * 100))


def _finding_card(finding, implicit=False):
    flags = ['<span class="flag draft">черновик</span>' if finding.get("provisional")
             else '<span class="flag ok">проверено</span>']
    anchors = ", ".join(finding.get("anchors") or [])
    anchor_note = anchors or ("—"
                              + (" · неявные: " + ", ".join(implicit) if implicit else ""))
    rows = [
        ("правило", f"{finding['rule_id']} · версия {finding['rule_version']}"),
        ("ступень", finding.get("step") or "—"),
        ("потолок", f"{finding.get('confidence_ceiling', 0):.2f}"),
        ("приор", f"{finding.get('confidence_prior', 0):.2f}"),
        ("якоря", anchor_note),
    ]
    rows_html = "".join(f"<div><span>{esc(k)}</span><span>{esc(v)}</span></div>" for k, v in rows)
    return (
        f'<div class="card" data-node="{esc(finding["finding_id"])}">'
        f'<div class="kind"><span>улика {esc(finding["rule_id"])}</span>{"".join(flags)}</div>'
        f'<h4>{esc(finding.get("title"))}</h4>'
        f'<p class="note">{esc(finding.get("inference"))}</p>'
        f'<div class="rows">{rows_html}</div>'
        "</div>"
    )


def _claim_card(claim):
    return (
        f'<div class="card" data-node="{esc(claim["claim_id"])}">'
        f'<div class="kind"><span>утверждение {esc(claim["claim_id"])}</span>'
        f'<span class="flag {"ok" if claim.get("confidence", 0) >= 0.5 else "warn"}">'
        f'{claim.get("confidence", 0):.0%}</span></div>'
        f'<h4>{esc(claim.get("text"))}</h4>'
        f'<div class="rows">'
        f'<div><span>ступень</span><span>{esc(claim.get("step") or "—")}</span></div>'
        f'<div><span>основание</span><span>{esc(", ".join(s.get("finding_id", "") for s in claim.get("support") or []))}</span></div>'
        f'<div><span>отрицание</span><span>{esc((claim.get("refutation") or {}).get("outcome") or "—")}</span></div>'
        "</div></div>"
    )


def _version_card(hypothesis):
    weight = hypothesis.get("log_odds")
    bar = ""
    if isinstance(weight, (int, float)):
        bar = f'<div class="bar logodds"><i style="width:{_weight_width(weight)}%"></i></div>'
    return (
        f'<div class="card" data-node="{esc(hypothesis["hypothesis_id"])}">'
        f'<div class="kind"><span>версия {esc(hypothesis["hypothesis_id"])}</span>'
        f'<span class="flag {"warn" if hypothesis.get("status") == "rejected" else "ok"}">'
        f'{esc(hypothesis.get("status") or "open")}</span></div>'
        f'<h4>{esc(hypothesis.get("text"))}</h4>'
        f'<div class="rows">'
        f'<div><span>утверждения</span><span>{esc(", ".join(hypothesis.get("claims") or []))}</span></div>'
        f'<div><span>вес</span><span>{weight if weight is not None else "—"}</span></div>'
        "</div>" + bar + "</div>"
    )


def _anchor_text(finding, implicit_by_finding=None):
    anchors = ", ".join(finding.get("anchors") or [])
    implicit = (implicit_by_finding or {}).get(finding["finding_id"]) or []
    parts = [anchors] if anchors else []
    if implicit:
        parts.append("неявные: " + ", ".join(implicit))
    return " · ".join(parts) if parts else "—"


def _facts_table(scene_facts):
    rows = []
    for fact in scene_facts:
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(fact["fact_id"])}</td>'
            f'<td>{esc(fact["kind"])}</td>'
            f'<td>{esc(fact["text"])}</td>'
            f'<td class="mono">{esc(", ".join(fact.get("about") or []))}</td>'
            f'<td class="sub">{esc(fact.get("basis"))}</td>'
            f'<td class="mono">{fact.get("confidence", 0):.2f}</td>'
            "</tr>"
        )
    return (
        '<table class="grid"><thead><tr><th>Факт</th><th>Тип</th><th>Что видно</th>'
        "<th>Объекты</th><th>Чем подтверждён</th><th>Уверенность</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>"
    )


def _findings_table(findings, implicit_by_finding=None):
    rows = []
    for f in findings:
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(f["finding_id"])}</td>'
            f'<td class="mono">{esc(f["rule_id"])} v{f["rule_version"]}</td>'
            f'<td>{esc(f.get("title"))}</td>'
            f'<td>{esc(f.get("step") or "—")}</td>'
            f'<td class="mono">{f.get("confidence_ceiling", 0):.2f}</td>'
            f'<td>{"черновик" if f.get("provisional") else "проверено"}</td>'
            f'<td>{esc(f.get("inference"))}</td>'
            f'<td class="mono">{esc(_anchor_text(f, implicit_by_finding))}</td>'
            f'<td class="sub">{esc(f.get("sources")[0].get("ref", "")[:90]) if f.get("sources") else "—"}</td>'
            "</tr>"
        )
    return (
        '<table class="grid"><thead><tr><th>Улика</th><th>Правило</th><th>Название</th>'
        "<th>Ступень</th><th>Потолок</th><th>Статус</th><th>Вывод</th><th>Якоря</th><th>Источник</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _findings_dossiers(findings, implicit_by_finding=None):
    blocks = []
    for f in findings:
        implicit = (implicit_by_finding or {}).get(f["finding_id"]) or []
        sources = "".join(
            f'<p class="src"><b>источник:</b> {esc(s.get("ref"))}<br>'
            f'<span class="sub">{esc(s.get("note"))}</span>'
            f'{" · подтверждён" if s.get("verified") else " · не подтверждён"}</p>'
            for s in (f.get("sources") or [])
        )
        confounds = "".join(f"<li>{esc(c)}</li>" for c in (f.get("confounds") or []))
        exceptions = "".join(f"<li>{esc(c)}</li>" for c in (f.get("exceptions") or []))
        implicit_html = ""
        if implicit:
            implicit_html = (
                f'<p><b>Неявный якорь (по предикату):</b> {esc(", ".join(implicit))} — правило сработало '
                "на этих объектах, но в <code>anchors</code> правила их нет, поэтому улика "
                "не привязана к сцене формально.</p>"
            )
        blocks.append(
            f'<div class="d"><h4>{esc(f.get("title"))}</h4>'
            f'<div class="meta">{esc(f["rule_id"])} · версия {f["rule_version"]} · '
            f'{esc(f.get("domain"))} · потолок {f.get("confidence_ceiling", 0):.2f} · '
            f'{"черновик" if f.get("provisional") else "проверено"}</div>'
            f'<p><b>Вывод:</b> {esc(f.get("inference"))}</p>'
            f'<p><b>Якоря:</b> {esc(_anchor_text(f, implicit_by_finding))}</p>'
            f"{implicit_html}"
            f'<p><b>Оговорки улики:</b></p><ul>{confounds}</ul>'
            f'<p><b>Исключения:</b></p><ul>{exceptions}</ul>'
            f'<p><b>Опровержение:</b> {esc((f.get("falsification") or {}).get("physical_test", "—"))}</p>'
            f"{sources}</div>"
        )
    return '<div class="dossier">' + "".join(blocks) + "</div>"


def _claims_panel(claims, findings_by_id):
    blocks = []
    for c in claims:
        support = ", ".join(s.get("finding_id", "") for s in c.get("support") or [])
        rules = ", ".join(sorted({
            findings_by_id[s["finding_id"]]["rule_id"]
            for s in c.get("support") or [] if s.get("finding_id") in findings_by_id
        }))
        confounds = "".join(f"<li>{esc(x)}</li>" for x in (c.get("confounds") or []))
        refutation = c.get("refutation") or {}
        outcome = refutation.get("outcome")
        flag = {"survived": "ok", "refuted": "bad"}.get(outcome, "warn")
        label = {"survived": "вывод устоял", "refuted": "вывод опровергнут"}.get(outcome, "не решено")
        provisional = '<span class="flag draft">provisional</span>' if c.get("provisional") else ""
        blocks.append(
            f'<div class="claim"><div class="cid">УТВЕРЖДЕНИЕ {esc(c["claim_id"])}</div>'
            f'<h4>{esc(c.get("text"))}</h4>'
            f'<div class="meta"><span class="chip">ступень {esc(c.get("step") or "—")}</span>'
            f'<span class="chip">уверенность {c.get("confidence", 0):.0%}</span>'
            f'<span class="chip">основание {esc(support)}</span>'
            f'<span class="chip">правила {esc(rules or "—")}</span>'
            f'<span class="flag {flag}">{esc(label)}</span>'
            f'{provisional}</div>'
            f'<div class="bar conf"><i style="width:{int(c.get("confidence", 0) * 100)}%"></i></div>'
            + (f"<ul>{confounds}</ul>" if confounds else "")
            + (f'<div class="quote"><b>Отрицание:</b> «{esc(refutation.get("negation"))}» — {esc(label)}.'
               f'{("<br>" + esc(refutation.get("note"))) if refutation.get("note") else ""}</div>'
               if refutation.get("negation") else "")
            + (f'<p class="sub" style="margin:9px 0 0"><b>Что опровергло бы:</b> {esc(c.get("falsification"))}</p>'
               if c.get("falsification") else "")
            + "</div>"
        )
    return '<div class="cols2">' + "".join(blocks) + "</div>"


def _versions_panel(hypotheses, questions):
    blocks = []
    for h in hypotheses:
        disc = h.get("discriminator") or {}
        weight = h.get("log_odds")
        bar = ""
        if isinstance(weight, (int, float)):
            bar = (f'<div class="bar logodds"><i style="width:{_weight_width(weight)}%"></i></div>'
                   f'<p class="sub">log-odds {weight}</p>')
        disc_html = ""
        if disc.get("question"):
            disc_html = (
                '<div class="disc"><b>Что разведёт:</b> ' + esc(disc["question"])
                + (f'<br><b>Подтвердит:</b> {esc(disc.get("would_confirm"))}' if disc.get("would_confirm") else "")
                + (f'<br><b>Опровергнёт:</b> {esc(disc.get("would_refute"))}' if disc.get("would_refute") else "")
                + "</div>"
            )
        kill = "".join(
            f'<p class="sub">убита: {esc(k.get("rule_id"))} — {esc(k.get("note"))}</p>'
            for k in (h.get("kill_log") or [])
        )
        blocks.append(
            f'<div class="ver"><div class="cid" style="font:700 11px/1 system-ui;letter-spacing:.16em;color:#6a5947">'
            f'ВЕРСИЯ {esc(h["hypothesis_id"])}</div>'
            f'<h4>{esc(h.get("text"))}</h4>'
            f'<div class="meta" style="display:flex;gap:8px;flex-wrap:wrap;font-size:11.5px">'
            f'<span class="chip">статус {esc(h.get("status") or "open")}</span>'
            f'<span class="chip">утверждения {esc(", ".join(h.get("claims") or []))}</span></div>'
            + bar + disc_html + kill + "</div>"
        )
    if questions:
        items = "".join(
            f'<li><b>{esc(q.get("question"))}</b>'
            + (f'<br><span class="sub">зачем: {esc(q.get("why"))}</span>' if q.get("why") else "")
            + (f'<br><span class="sub">затрагивает версий: {esc(", ".join(q.get("hypotheses") or []))}</span>'
               if q.get("hypotheses") else "")
            + "</li>"
            for q in questions
        )
        blocks.append(f'<div class="ver"><h4>Что снять дальше</h4><ul style="margin:6px 0 0;padding-left:18px">{items}</ul></div>')
    return '<div class="cols2">' + "".join(blocks) + "</div>"


def _rerun_panel(ledger_text, commands):
    cmds = "".join(
        f'<div class="cmd"><code>{esc(c)}</code>'
        f'<button data-copy="#cmd-{i}">копировать</button>'
        f'<textarea id="cmd-{i}" style="display:none">{esc(c)}</textarea></div>'
        for i, c in enumerate(commands)
    )
    return (
        '<div class="rerun"><h3 style="margin:0 0 6px;font-size:19px">Переразбор</h3>'
        '<p class="sub" style="margin:0 0 14px;color:#6a5947">Леджер можно править прямо здесь и выгрузить, '
        "но истина остаётся в движке: правка текста здесь ничего не меняет в разборе, "
        "пока леджер не перезапущен движком.</p>"
        '<div class="toolbar">'
        '<button id="download">выгрузить ledger.json</button>'
        '<button data-copy="#ledger">скопировать леджер</button>'
        "</div>"
        f'<textarea id="ledger">{esc(ledger_text)}</textarea>'
        f"{cmds}</div>"
    )


def build(scene, findings, ledger, hypotheses=None, questions=None, verdict=None,
          narrative="", title="Доска разбора", subtitle="", commands=None, meta=None, rules=None,
          scene_facts=None):
    """Собрать самодостаточную HTML-страницу доски."""
    findings = findings or []
    claims = ledger.get("claims") or []
    hypotheses = hypotheses or []
    questions = questions or []
    commands = commands or []
    findings_by_id = {f["finding_id"]: f for f in findings}
    index = _element_index(scene)
    rules_by_id = {rule.id: rule for rule in (rules or [])}

    used_elements = set()
    links = []
    implicit_by_finding = {}
    for f in findings:
        explicit = list(f.get("anchors") or [])
        implicit = []
        if not explicit:
            implicit = implicit_anchors(scene, rules_by_id.get(f["rule_id"]))
        implicit_by_finding[f["finding_id"]] = implicit
        for anchor in explicit:
            used_elements.add(anchor)
            links.append({"from": anchor, "to": f["finding_id"], "label": f["rule_id"], "kind": "scene", "dir": 1})
        for anchor in implicit:
            used_elements.add(anchor)
            links.append({"from": anchor, "to": f["finding_id"], "label": f["rule_id"] + " неявно",
                          "kind": "scene", "dir": -1})
    for c in claims:
        for s in c.get("support") or []:
            fid = s.get("finding_id")
            if fid in findings_by_id:
                links.append({"from": fid, "to": c["claim_id"], "label": c["claim_id"], "kind": "evid", "dir": 1})
    for h in hypotheses:
        for cid in h.get("claims") or []:
            links.append({"from": cid, "to": h["hypothesis_id"], "label": h["hypothesis_id"], "kind": "ver", "dir": 1})

    scene_cards = []
    gap_cards = []
    for element_id, (collection, item) in index.items():
        if collection == "surfaces":
            continue
        label = _element_label(collection, item)
        if element_id in used_elements:
            scene_cards.append(_node(element_id, collection[:-1], label, ""))
        elif collection == "regions":
            gap_cards.append(_node(element_id, "след без правила", label,
                                   "Ни одно правило не сработало на этом следе: находки не будет, "
                                   "пока для него нет правила.", extra="gap"))

    scene_html = "".join(scene_cards) + "".join(gap_cards)
    if not scene_html:
        scene_html = '<div class="card"><h4>Следов в графе нет</h4><p class="note">Улик не будет.</p></div>'

    tabs = "".join(f'<div class="tab{" on" if key == "board" else ""}" data-tab="{key}">{label}</div>'
                   for key, label in TAB_BAR)

    meta_items = meta or {}
    badges = "".join(f'<div class="badge {meta_items.get("tone", "")}"><span>{esc(k)}</span><b>{esc(v)}</b></div>'
                     for k, v in meta_items.get("badges", []))

    doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <div class="kicker">ЭЛЕМЕНТАРНО · протокол доказательности</div>
    <h1>{esc(title)}</h1>
    <div class="sub">{esc(subtitle)}</div>
    <div class="badges">{badges}</div>
  </header>
  <nav class="tabs">{tabs}</nav>

  <section class="panel on" id="board">
    <div class="toolbar"><button id="reset">показать всё</button>
      <span class="sub" style="color:#b49f81;align-self:center;font-size:12.5px">
        нити: золотая — след ведёт к улике, красная — улика к утверждению, синяя — утверждение к версии;
        клик по карточке оставляет только связанные</span></div>
    <div class="board" id="board">
      <svg class="strings" id="strings"></svg>
      <div class="cols">
        <div class="col"><h3>Следы и предметы</h3><div class="stack">{scene_html}</div></div>
        <div class="col"><h3>Улики</h3><div class="stack">{''.join(_finding_card(f, implicit_by_finding.get(f['finding_id'])) for f in findings)}</div></div>
        <div class="col"><h3>Утверждения</h3><div class="stack">{''.join(_claim_card(c) for c in claims)}</div></div>
        <div class="col"><h3>Версии</h3><div class="stack">{''.join(_version_card(h) for h in hypotheses)}</div></div>
      </div>
    </div>
  </section>

  <section class="panel" id="facts">
    <h2 class="panel-h">Факты</h2>
    <p class="panel-sub">Что видно в кадре и чем это подтверждено. Факты не знают ни про криминалистику,
      ни про домен: это предметы, их состояния, количества и связи.</p>
    {_facts_table(scene_facts or [])}
  </section>

  <section class="panel" id="findings">
    <h2 class="panel-h">Находки</h2>
    <p class="panel-sub">Полный список сработавших правил: что они утверждают, на каких якорях держатся,
      чем ограничены и каким источником подкреплены.</p>
    {_findings_table(findings, implicit_by_finding)}
    <div style="height:22px"></div>
    {_findings_dossiers(findings, implicit_by_finding)}
  </section>

  <section class="panel" id="claims">
    <h2 class="panel-h">Утверждения</h2>
    <p class="panel-sub">Каждое утверждение ссылается на улику, ограничено её потолком
      и атаковано отрицанием: исход отрицания — часть вывода, а не формальность.</p>
    {_claims_panel(claims, findings_by_id)}
  </section>

  <section class="panel" id="versions">
    <h2 class="panel-h">Версии</h2>
    <p class="panel-sub">Версии различаются весом улик и различающим вопросом.
      Без разделителя конкурирующие версии остаются неразличимыми.</p>
    {_versions_panel(hypotheses, questions)}
  </section>

  <section class="panel" id="rerun">
    <h2 class="panel-h">Переразбор</h2>
    <p class="panel-sub">Правьте леджер, выгружайте и запускайте движок: страница показывает разбор,
      истину считает движок.</p>
    {_rerun_panel(json.dumps(ledger, ensure_ascii=False, indent=2), commands)}
    <div class="note-box">Ответ движка на этот разбор:</div>
    <div class="narrative">{esc(narrative)}</div>
  </section>
</div>
<script>
window.__LINKS__ = {json.dumps(links, ensure_ascii=False)};
{JS}
</script>
</body>
</html>
"""
    return doc
