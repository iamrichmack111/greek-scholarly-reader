#!/usr/bin/env python3
"""Greek parallel citation reader with transparent lexical highlighting."""
import argparse, html, json, pathlib, re, sqlite3, unicodedata, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GREEK_MAP = {"magus": ("μάγος", "μαγ"), "magi": ("μάγος", "μαγ"), "magian": ("μάγος", "μαγ")}

def esc(value): return html.escape(str(value), quote=True)
def normalize(value):
    value = unicodedata.normalize('NFD', value.casefold())
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    return value.replace('ς', 'σ')

def highlight_literal(text, term):
    if not term: return esc(text)
    pieces = re.split('(' + re.escape(term) + ')', text, flags=re.I)
    return ''.join('<mark>' + esc(p) + '</mark>' if p.casefold() == term.casefold() else esc(p) for p in pieces)

def greek_html(text, query, greek_hint=''):
    """Highlight only visible Greek matches; each Greek token is clickable."""
    targets = [normalize(x) for x in re.findall(r'[^\W\d_]+', query, re.UNICODE) if re.search('[\u0370-\u03ff\u1f00-\u1fff]', x)]
    explicit = normalize(greek_hint.strip()) if greek_hint else ''
    candidates = [explicit] if explicit else targets
    def span(match):
        word = match.group(0)
        nw = normalize(word)
        matches = any(nw == t or (explicit and len(t) >= 3 and nw.startswith(t)) for t in candidates)
        label = '<mark>' + esc(word) + '</mark>' if matches else esc(word)
        return '<span class="greek-word" data-word="' + esc(word) + '" tabindex="0" role="button">' + label + '</span>'
    # Split preserving HTML escaping for punctuation; avoid matching Latin words in mixed-script text.
    pattern = re.compile(r'[\u0370-\u03ff\u1f00-\u1fff]+(?:[\u0300-\u036f]*[\u0370-\u03ff\u1f00-\u1fff]+)*')
    out=[]; last=0
    for m in pattern.finditer(text):
        out.append(esc(text[last:m.start()])); out.append(span(m)); last=m.end()
    out.append(esc(text[last:])); return ''.join(out)

CSS = '''<style>
:root{color-scheme:dark}body{background:#111823;color:#e3e5ed;font:16px system-ui;margin:3% auto;max-width:1540px;padding:0 24px}h1{color:#edc96a}
form{display:flex;gap:12px;flex-wrap:wrap}input{flex:1;min-width:180px;padding:12px;background:#1f2c40;color:white;border:1px solid #5c667a;border-radius:8px}button{padding:12px;background:#b18d35;border:0;border-radius:8px;cursor:pointer}
.row{margin:20px 0;background:#1a2636;border:1px solid #3a4b60;border-radius:10px;padding:18px}.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}.two article{line-height:1.85;white-space:pre-wrap;min-width:0}.grc{font-size:21px;color:#e8dba8}mark{background:#e9c450;color:#161616;border-radius:3px}small,.muted{color:#aab6c8}a{color:#d7c077}.greek-word{cursor:pointer;border-radius:3px}.greek-word:hover{outline:1px solid #b18d35;background:#324057}.wrap{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px}.inspector{position:sticky;top:12px;align-self:start;background:#202e42;padding:17px;border:1px solid #6e7990;border-radius:10px;max-height:80vh;overflow:auto}.chips{display:flex;gap:5px;flex-wrap:wrap}.chip{background:#344a60;color:#fff;padding:6px;border-radius:6px}.status{color:#f1d17c} .lex{padding:9px 0;border-top:1px solid #526075;overflow-wrap:anywhere}
@media(max-width:1050px){.wrap{grid-template-columns:1fr}.inspector{position:static}.two{grid-template-columns:1fr}}
.word-popup{position:fixed;z-index:10000;width:min(420px,calc(100vw - 24px));max-height:75vh;overflow:auto;padding:17px;box-sizing:border-box;box-shadow:0 16px 55px #000c;background:#25344c;border:2px solid #e9c450;border-radius:12px;color:#f1ebdd}.word-popup[hidden]{display:none}.popup-head{display:flex;align-items:center;justify-content:space-between;gap:12px;color:#e9c450}.popup-close{font-size:23px;color:#fff;background:#495c76;padding:3px 12px}.greek-word.is-selected{outline:2px solid #f5d36c}.word-popup .lex{font-size:14px;line-height:1.5}
</style>'''
JS = r'''<script>
(function(){
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let active=null, serial=0;
function box(){return document.getElementById('word-popup')}
function close(){box().hidden=true;if(active)active.classList.remove('is-selected');active=null}
function place(){const p=box();if(p.hidden)return;const rect=active?.getBoundingClientRect();if(!rect||innerWidth<700){p.style.left='auto';p.style.right='12px';p.style.top='12px';return}const w=Math.min(420,innerWidth-24);let x=rect.right+12;if(x+w>innerWidth-12)x=rect.left-w-12;if(x<12)x=innerWidth-w-12;p.style.left=x+'px';p.style.right='auto';p.style.top=Math.max(12,Math.min(rect.top,innerHeight-140))+'px'}
function show(body){const p=box();p.hidden=false;p.innerHTML='<div class="popup-head"><strong>Greek Word Inspector</strong><button type="button" class="popup-close" aria-label="Close inspector">×</button></div><div>'+body+'</div>';const side=document.getElementById('word-info');if(side)side.innerHTML=body;place()}
async function inspect(word,element){word=String(word||'').trim();if(!word)return;if(active)active.classList.remove('is-selected');active=element||null;if(active)active.classList.add('is-selected');let id=++serial;show('<p>Looking up <b>'+esc(word)+'</b>…</p>');try{const response=await fetch('/api/word?word='+encodeURIComponent(word),{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);const data=await response.json();if(id!==serial)return;let body='<h3>'+esc(word)+'</h3><small>Normalized: '+esc(data.normalized)+'</small>';if(data.warning)body+='<p class="status">Dictionary warning: '+esc(data.warning)+'</p>';if(data.entries?.length){for(const item of data.entries)body+='<div class="lex"><strong>'+esc(item.headword)+'</strong> · '+esc(item.dictionary)+'<p>'+esc(String(item.definition||'').slice(0,1800))+'</p></div>'}else body+='<p>No exact dictionary headword found; this may be an inflected form.</p>';if(data.suggestions?.length){body+='<p>Suggestions:</p><div class="chips">';for(const item of data.suggestions)body+='<button type="button" class="chip" data-suggestion="'+esc(item)+'">'+esc(item)+'</button>';body+='</div>'}body+='<p><a href="/?q='+encodeURIComponent(word)+'">Search passages ↗</a></p>';show(body)}catch(e){if(id===serial)show('<p class="status">Lookup failed: '+esc(e.message)+'</p>')}}
document.addEventListener('click',e=>{if(e.target.closest('.popup-close')){close();return}const suggestion=e.target.closest('[data-suggestion]');if(suggestion){inspect(suggestion.dataset.suggestion,null);return}const token=e.target.closest('.greek-word');if(token)inspect(token.dataset.word,token)});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();if((e.key==='Enter'||e.key===' ')&&e.target.matches('.greek-word')){e.preventDefault();inspect(e.target.dataset.word,e.target)}});addEventListener('resize',place);
})();
</script>'''
class Handler(BaseHTTPRequestHandler):
    def send_data(self, data, mimetype='text/html; charset=utf-8', status=200):
        body=(data if isinstance(data,bytes) else data.encode('utf-8'))
        self.send_response(status); self.send_header('Content-Type',mimetype);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path); params=urllib.parse.parse_qs(path.query)
        if path.path=='/api/word':return self.word_api(params.get('word',[''])[0])
        if path.path=='/api/search':return self.search_api(params.get('q',[''])[0])
        if path.path!='/':return self.send_data('Not found',status=404)
        q=params.get('q',[''])[0].strip()[:100]; greek_hint=params.get('greek',[''])[0].strip()[:80]
        if not greek_hint and q.casefold() in GREEK_MAP:
            suggested, stem=GREEK_MAP[q.casefold()];greek_hint=stem
        else:suggested=None
        parts=['<!doctype html><meta charset="utf-8"><title>Greek Parallel Reader</title>',CSS,'<h1>Greek Parallel Reader — Citation-aligned texts</h1>',
            '<p class="muted">Greek/English are matched by cited section, not by individual word. Yellow shows literal matches or an explicitly labeled Greek lexical candidate.</p>',
            '<form><input name="q" value="'+esc(q)+'" placeholder="Greek or English search"><input name="greek" value="'+esc(greek_hint)+'" placeholder="Greek word or stem to highlight"><button>Search</button></form>']
        if suggested:parts.append('<p class="status">Greek lexical suggestion for “'+esc(q)+'”: '+esc(suggested)+' — highlighting forms beginning '+esc(greek_hint)+'. This is a spelling aid, not verified word alignment.</p>')
        parts.append('<div class="wrap"><main>')
        if q:
            with sqlite3.connect(self.server.db,uri=True) as connection:
                try:rows=connection.execute('''SELECT a.work_id,a.citation,a.english,a.greek,a.english_file,a.greek_file FROM aligned_fts f JOIN aligned a ON a.rowid=f.rowid WHERE aligned_fts MATCH ? LIMIT 35''',('"'+q.replace('"','""')+'"',)).fetchall()
                except sqlite3.OperationalError:rows=[]
            parts.append('<p>'+str(len(rows))+' results displayed (maximum 35).</p>')
            for work,cite,en,gr,ef,gf in rows:
                parts.append('<div class="row"><b>'+esc(work)+' · '+esc(cite)+'</b><br><small>'+esc(ef)+' ↔ '+esc(gf)+'</small><div class="two"><article><h3>English</h3>'+highlight_literal(en,q)+'</article><article class="grc"><h3>Greek (same cited section)</h3>'+greek_html(gr,q,greek_hint)+'</article></div></div>')
        parts.append('</main><aside class="inspector"><h2>Greek Word Inspector</h2><div id="word-info"><p>Click any Greek word to inspect its dictionary entry and suggestions.</p></div></aside></div>')
        parts.append('<div id="word-popup" class="word-popup" role="dialog" aria-label="Greek word information" hidden></div>');parts.append(JS);self.send_data(''.join(parts))
    def word_api(self, word):
        word=word.strip()[:80];result={'word':word,'normalized':normalize(word),'entries':[],'suggestions':[]}
        if not word:return self.send_data(json.dumps({'error':'Empty word'}),'application/json',400)
        if self.server.lexicon:
            try:
                with sqlite3.connect(self.server.lexicon,uri=True) as c:
                    c.row_factory=sqlite3.Row; normalized=normalize(word)
                    result['entries']=[dict(row) for row in c.execute('SELECT dictionary,headword,definition FROM lexicon WHERE head_norm=? LIMIT 5',(normalized,))]
                    seed=normalized[:max(1,min(3,len(normalized)-1))]
                    candidates=c.execute('SELECT DISTINCT headword,head_norm FROM lexicon WHERE head_norm>=? AND head_norm<? LIMIT 300',(seed,seed+'\U0010ffff')).fetchall()
                    import difflib
                    ranked=sorted(candidates,key=lambda r:difflib.SequenceMatcher(None,normalized,r['head_norm']).ratio(),reverse=True)
                    result['suggestions']=[r['headword'] for r in ranked if r['head_norm']!=normalized][:8]
            except sqlite3.Error as ex:result['warning']=str(ex)
        self.send_data(json.dumps(result,ensure_ascii=False),'application/json; charset=utf-8')
    def search_api(self,q):
        rows=[]
        if q:
            with sqlite3.connect(self.server.db,uri=True) as c:
                c.row_factory=sqlite3.Row
                try:rows=[dict(x) for x in c.execute('SELECT a.* FROM aligned_fts JOIN aligned a ON a.rowid=aligned_fts.rowid WHERE aligned_fts MATCH ? LIMIT 20',('"'+q.replace('"','""')+'"',))]
                except sqlite3.OperationalError:pass
        self.send_data(json.dumps(rows,ensure_ascii=False),'application/json; charset=utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=pathlib.Path,default=pathlib.Path.home()/'GREEK-LIBRARY');parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--port',type=int,default=8798);args=parser.parse_args()
    base=args.base.expanduser().resolve(); db=base/'data/alignments_v6.db';lex=base/'data/scholarly.db'
    if not db.exists():raise SystemExit('Missing alignment database: '+str(db))
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.db='file:'+urllib.parse.quote(str(db))+'?mode=ro';server.lexicon='file:'+urllib.parse.quote(str(lex))+'?mode=ro' if lex.exists() else None
    print('Greek Parallel Reader http://'+args.host+':'+str(args.port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
