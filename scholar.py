#!/usr/bin/env python3
"""Standalone source-aware Greek library; does not edit the earlier Greek Esoterica database."""
import argparse, hashlib, json, re, sqlite3, sys, unicodedata, xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path.home() / 'GREEK-LIBRARY'
DB_REL = 'data/scholarly.db'

def norm(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', (s or '').casefold()) if unicodedata.category(c) != 'Mn')
    return unicodedata.normalize('NFC', s).replace('ς','σ')
def clean(s): return re.sub(r'\s+', ' ', s or '').strip()
def lname(tag): return tag.rsplit('}',1)[-1] if isinstance(tag,str) else ''
def txt(e): return clean(''.join(e.itertext())) if e is not None else ''
def find_text(root,tag):
    for e in root.iter():
        if lname(e.tag)==tag and txt(e): return txt(e)
    return ''
def ftsquery(q):
    words=re.findall(r'[^\W_]+',norm(q),re.UNICODE)
    return ' '.join('"'+w+'"' for w in words[:24])

def connect(base):
    path=base/DB_REL; path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=60)
    c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA busy_timeout=60000')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS works(edition_id TEXT PRIMARY KEY, author TEXT, title TEXT, language TEXT, source TEXT, edition TEXT);
    CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY, edition_id TEXT NOT NULL, reference TEXT, original TEXT NOT NULL, normalized TEXT NOT NULL, source_path TEXT NOT NULL, UNIQUE(source_path, reference, original));
    CREATE INDEX IF NOT EXISTS passages_edition ON passages(edition_id);
    CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(original,normalized,content='passages',content_rowid='id', tokenize='unicode61');
    CREATE TABLE IF NOT EXISTS lexicon(id INTEGER PRIMARY KEY, dictionary TEXT NOT NULL, headword TEXT NOT NULL, head_norm TEXT NOT NULL, definition TEXT NOT NULL, source_path TEXT, source_entry TEXT, UNIQUE(dictionary,source_path,source_entry));
    CREATE INDEX IF NOT EXISTS lex_head ON lexicon(head_norm);
    CREATE VIRTUAL TABLE IF NOT EXISTS lexicon_fts USING fts5(headword,head_norm,definition,content='lexicon',content_rowid='id',tokenize='unicode61');
    CREATE TABLE IF NOT EXISTS completed_files(path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, kind TEXT, records INTEGER);
    ''')
    return c

def read_xml(p):
    try:return ET.parse(p).getroot()
    except (ET.ParseError, OSError, UnicodeError):return None

def cts_info(p):
    # Resolve edition to human-readable title/author from CTS metadata; do not guess titles.
    edition=p.stem; workdir=p.parent; authordir=workdir.parent
    author=title=''
    for meta, wanted in ((authordir/'__cts__.xml','groupname'),(workdir/'__cts__.xml','title')):
        if not meta.is_file():continue
        root=read_xml(meta)
        if root is None:continue
        if wanted=='groupname':
            author=find_text(root,'groupname') or find_text(root,'name')
        else:
            # Prefer edition-specific label, then work title.
            for el in root.iter():
                if lname(el.tag) in ('edition','translation') and (el.get('urn','').endswith(edition) or edition in el.get('urn','')):
                    title=find_text(el,'label');break
            title=title or find_text(root,'title') or find_text(root,'label')
    if not title or not author:
        root=read_xml(p)
        if root is not None:
            title=title or find_text(root,'title')
            author=author or find_text(root,'author')
    return author or authordir.name, title or workdir.name

def passage_rows(path):
    root=read_xml(path)
    if root is None:return
    body=next((e for e in root.iter() if lname(e.tag)=='body'),None)
    if body is None:return
    # Linear traversal with ancestor tracking, unlike expensive pairwise scans.
    # Top-level p/ab/l are passages; descendants aren't duplicated.
    count=0
    def walk(node,inside=False,refprefix=''):
        nonlocal count
        tag=lname(node.tag)
        ref=node.get('n') or refprefix
        unit=tag in ('p','ab','l')
        if unit and not inside:
            content=txt(node)
            if len(content)>1:
                count+=1
                yield (str(ref or count),content)
            return
        for ch in node:
            yield from walk(ch,inside or unit,ref)
    produced=False
    for row in walk(body):
        produced=True;yield row
    if not produced:
        s=txt(body)
        if s:yield ('1',s)

def import_texts(base, conn, batch):
    total=0
    for repo in ('perseus','first1k'):
        root=base/'classical'/repo/'data'
        if not root.exists():print('MISSING',root);continue
        paths=sorted(p for p in root.rglob('*.xml') if p.name!='__cts__.xml')
        print(f'{repo}: {len(paths):,} XML candidates',flush=True)
        for n,p in enumerate(paths,1):
            rel=str(p.relative_to(base));stat=p.stat()
            old=conn.execute('SELECT size,mtime_ns FROM completed_files WHERE path=?',(rel,)).fetchone()
            if old==(stat.st_size,stat.st_mtime_ns):continue
            edition=p.stem
            author,title=cts_info(p)
            language='grc' if '-grc' in p.stem else 'eng' if '-eng' in p.stem else 'und'
            conn.execute('INSERT OR REPLACE INTO works VALUES(?,?,?,?,?,?)',(edition,author,title,language,repo,''))
            count=0
            for reference,original in passage_rows(p):
                cur=conn.execute('INSERT OR IGNORE INTO passages(edition_id,reference,original,normalized,source_path) VALUES(?,?,?,?,?)',(edition,reference,original,norm(original),rel))
                if cur.rowcount:count+=1;total+=1
                if count and count%batch==0:conn.commit()
            conn.execute('INSERT OR REPLACE INTO completed_files VALUES(?,?,?,?,?)',(rel,stat.st_size,stat.st_mtime_ns,'text',count))
            conn.commit()
            if n%100==0 or count>1000:print(f'[{repo}] {n}/{len(paths)} | {count} new passages in {p.name}',flush=True)
    print('New passages:',total)

def lex_entries(root):
    # LSJ/Perseus TEI frequently stores entry at <div2>; Woodhouse may use <entry>.
    for el in root.iter():
        if lname(el.tag) not in ('div2','entry','entryFree'):continue
        head=next((txt(c) for c in el.iter() if lname(c.tag) in ('head','form','orth') and txt(c)), '')
        head=head or el.get('key','')
        meaning=txt(el)
        if not head or not meaning:continue
        entry_id=el.get('id') or el.get('{http://www.w3.org/XML/1998/namespace}id') or hashlib.sha1(meaning.encode()).hexdigest()[:24]
        yield head,meaning[:30000],entry_id

def import_dicts(base,conn):
    paths=[]
    for name,d in [('LSJ',base/'dictionaries'/'lsj'),('WOODHOUSE',base/'dictionaries'/'woodhouse'),('PERSEUS_LEXICA',base/'dictionaries'/'perseus-lexica')]:
        if d.exists():paths += [(name,p) for p in sorted(d.rglob('*.xml')) if '.git' not in p.parts]
    counts={}
    for name,p in paths:
        rel=str(p.relative_to(base)); stat=p.stat()
        old=conn.execute('SELECT size,mtime_ns FROM completed_files WHERE path=?',(rel,)).fetchone()
        if old==(stat.st_size,stat.st_mtime_ns):continue
        root=read_xml(p)
        if root is None:
            print('SKIP unparsable dictionary XML',rel,flush=True);continue
        count=0
        for head,meaning,eid in lex_entries(root):
            cur=conn.execute('INSERT OR IGNORE INTO lexicon(dictionary,headword,head_norm,definition,source_path,source_entry) VALUES(?,?,?,?,?,?)',(name,head,norm(head),meaning,rel,eid))
            if cur.rowcount:count+=1
        conn.execute('INSERT OR REPLACE INTO completed_files VALUES(?,?,?,?,?)',(rel,stat.st_size,stat.st_mtime_ns,'dictionary',count))
        conn.commit();counts[name]=counts.get(name,0)+count
        if count:print('DICT',name,p.name,'new entries',count,flush=True)
    print('Dictionary import new entries:',counts)
    if not counts or not sum(counts.values()):print('NOTE: No new dictionary entries; check stats and source formats.')

def rebuild_fts(conn):
    print('Rebuilding FTS5 indexes (this may take some time)...',flush=True)
    conn.execute("INSERT INTO passages_fts(passages_fts) VALUES('rebuild')")
    conn.commit()
    conn.execute("INSERT INTO lexicon_fts(lexicon_fts) VALUES('rebuild')")
    conn.commit();print('FTS complete.',flush=True)

def search(base,q,limit,author='',language=''):
    conn=connect(base);conn.row_factory=sqlite3.Row
    match=ftsquery(q)
    if not match:return []
    sql='''SELECT p.id,w.author,w.title,w.language,w.source,p.edition_id,p.reference,p.original,p.source_path,bm25(passages_fts) AS score
    FROM passages_fts JOIN passages p ON p.id=passages_fts.rowid JOIN works w ON w.edition_id=p.edition_id
    WHERE passages_fts MATCH ?''';params=[match]
    if author:sql+=' AND w.author LIKE ?';params.append('%'+author+'%')
    if language:sql+=' AND w.language=?';params.append(language)
    sql+=' ORDER BY score LIMIT ?';params.append(limit)
    return [dict(r) for r in conn.execute(sql,params)]

def define(base,q,limit,contains=False):
    conn=connect(base);conn.row_factory=sqlite3.Row
    if contains:
        match=ftsquery(q)
        sql='''SELECT l.dictionary,l.headword,l.definition,l.source_path FROM lexicon_fts JOIN lexicon l ON l.id=lexicon_fts.rowid WHERE lexicon_fts MATCH ? ORDER BY bm25(lexicon_fts) LIMIT ?'''
        return [dict(r) for r in conn.execute(sql,(match,limit))]
    return [dict(r) for r in conn.execute('SELECT dictionary,headword,definition,source_path FROM lexicon WHERE head_norm=? LIMIT ?',(norm(q),limit))]

def stats(base):
    c=connect(base)
    return {'works':c.execute('SELECT COUNT(*) FROM works').fetchone()[0], 'passages':c.execute('SELECT COUNT(*) FROM passages').fetchone()[0], 'dictionary_entries':dict(c.execute('SELECT dictionary,COUNT(*) FROM lexicon GROUP BY dictionary').fetchall()), 'languages':dict(c.execute('SELECT language,COUNT(*) FROM works GROUP BY language').fetchall()),'completed_source_files':c.execute('SELECT COUNT(*) FROM completed_files').fetchone()[0]}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=BASE)
    sub=p.add_subparsers(dest='cmd',required=True)
    b=sub.add_parser('build');b.add_argument('--batch',type=int,default=1000);b.add_argument('--only',choices=['texts','dictionaries','all'],default='all')
    s=sub.add_parser('search');s.add_argument('query');s.add_argument('--author',default='');s.add_argument('--language',default='');s.add_argument('--limit',type=int,default=10)
    d=sub.add_parser('define');d.add_argument('word');d.add_argument('--contains',action='store_true');d.add_argument('--limit',type=int,default=5)
    sub.add_parser('stats');sub.add_parser('reindex')
    a=p.parse_args();base=a.base.expanduser().resolve()
    if a.cmd=='build':
        conn=connect(base)
        if a.only in ('all','texts'):import_texts(base,conn,max(100,a.batch))
        if a.only in ('all','dictionaries'):import_dicts(base,conn)
        rebuild_fts(conn);conn.close()
        print(json.dumps(stats(base),ensure_ascii=False,indent=2))
    elif a.cmd=='reindex':
        c=connect(base);rebuild_fts(c);c.close()
    elif a.cmd=='search':print(json.dumps(search(base,a.query,a.limit,a.author,a.language),ensure_ascii=False,indent=2))
    elif a.cmd=='define':print(json.dumps(define(base,a.word,a.limit,a.contains),ensure_ascii=False,indent=2))
    elif a.cmd=='stats':print(json.dumps(stats(base),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
