#!/usr/bin/env python3
"""Produces a REVIEW inventory; does not claim redistribution clearance."""
import argparse,csv,pathlib,sqlite3,subprocess,datetime,collections
A=argparse.ArgumentParser();A.add_argument('--base',type=pathlib.Path,default=pathlib.Path.home()/'GREEK-LIBRARY');A.add_argument('--output',type=pathlib.Path,default=pathlib.Path('source-license-review.csv'));a=A.parse_args()
base=a.base.expanduser();db=base/'data/scholarly.db'
if not db.exists():raise SystemExit(f'Missing {db}')
con=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
rows=con.execute("""SELECT w.source,w.edition_id,w.author,w.title,w.language, count(p.id) passage_count,
 min(p.source_path) source_path FROM works w LEFT JOIN passages p ON p.edition_id=w.edition_id
 GROUP BY w.edition_id ORDER BY w.source,w.author,w.title""")
with a.output.open('w',newline='',encoding='utf-8') as f:
 w=csv.writer(f);w.writerow(['source','edition_id','author','title','language','passage_count','source_path','redistribution_status','license_evidence_url','review_notes'])
 for row in rows:w.writerow(list(row)+['UNREVIEWED','',''])
print('Edition inventory:',a.output)
print('Every row remains UNREVIEWED; no bundled DB is cleared for redistribution.')
