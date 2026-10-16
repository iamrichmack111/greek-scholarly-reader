#!/usr/bin/env python3
"""Build exact citation-keyed parallel Greek/English passages from Perseus TEI XML."""
import argparse, pathlib, sqlite3, xml.etree.ElementTree as ET, re, unicodedata

def local(tag): return tag.rsplit('}',1)[-1]
def clean(text): return ' '.join(text.split())
def parts(path):
    root=ET.parse(path).getroot()
    def visit(node, book=None, chapter=None):
        if local(node.tag)=='div' and node.get('type','').lower()=='textpart':
            kind=node.get('subtype','').lower(); n=node.get('n')
            if kind=='book': book=n
            elif kind=='chapter': chapter=n
            elif kind=='section' and book and chapter and n and n.isdigit():
                value=clean(''.join(node.itertext()))
                if value: yield (book,chapter,n,value)
                return
        for child in node: yield from visit(child,book,chapter)
    return list(visit(root))

def build(base, db, limit=None):
    source=base/'classical/perseus/data'
    if not source.exists(): raise SystemExit(f'Missing {source}')
    db.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(db)
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript('''CREATE TABLE IF NOT EXISTS aligned (
        work_id TEXT NOT NULL, citation TEXT NOT NULL, book TEXT NOT NULL,
        chapter TEXT NOT NULL, section TEXT NOT NULL, english TEXT NOT NULL,
        greek TEXT NOT NULL, english_file TEXT NOT NULL, greek_file TEXT NOT NULL,
        PRIMARY KEY(work_id,citation));
    CREATE VIRTUAL TABLE IF NOT EXISTS aligned_fts USING fts5(english,greek,content='aligned',content_rowid='rowid');
    ''')
    pairs=0; matched=0; skipped=0
    for eng in sorted(source.glob('tlg*/tlg*/*eng*.xml')):
        # Exact same work + edition family, with an available Greek text.
        folder=eng.parent
        grcs=sorted(folder.glob('*grc*.xml'))
        if not grcs: continue
        grc=next((p for p in grcs if p.name.replace('grc','eng')==eng.name),grcs[0])
        work='.'.join(eng.name.split('.')[:2])
        try:
            es=parts(eng); gs=parts(grc)
        except ET.ParseError as exc:
            print(f'XML ERROR {eng}: {exc}',flush=True); skipped+=1;continue
        # Conservative: only keys unique within each edition can align.
        ed={}; gd={}; edup=set(); gdup=set()
        for b,c,s,t in es:
            k=f'{b}.{c}.{s}'
            if k in ed: edup.add(k)
            ed[k]=t
        for b,c,s,t in gs:
            k=f'{b}.{c}.{s}'
            if k in gd: gdup.add(k)
            gd[k]=t
        keys=(ed.keys() & gd.keys())-edup-gdup
        rows=[(work,k,*k.split('.'),ed[k],gd[k],str(eng.relative_to(base)),str(grc.relative_to(base))) for k in sorted(keys,key=lambda x: tuple((0, int(z)) if z.isdigit() else (1, z.casefold()) for z in x.split('.')))]
        with con:
            con.executemany('''INSERT INTO aligned(work_id,citation,book,chapter,section,english,greek,english_file,greek_file)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(work_id,citation) DO UPDATE SET
                english=excluded.english,greek=excluded.greek,english_file=excluded.english_file,greek_file=excluded.greek_file''',rows)
        pairs+=1;matched+=len(rows)
        print(f'{work} | EN={len(es)} GR={len(gs)} aligned={len(rows)}',flush=True)
        if limit and pairs>=limit:break
    # Rebuild FTS only after all INSERTS, avoiding row-by-row index overhead.
    with con: con.execute("INSERT INTO aligned_fts(aligned_fts) VALUES ('rebuild')")
    print(f'DONE: {pairs} edition pairs, {matched} matched sections, {skipped} XML errors, database={db}',flush=True)
    con.close()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--base',type=pathlib.Path,default=pathlib.Path.home()/'GREEK-LIBRARY');a.add_argument('--db',type=pathlib.Path);a.add_argument('--limit',type=int)
    args=a.parse_args();build(args.base,args.db or args.base/'data/alignments_v6.db',args.limit)
