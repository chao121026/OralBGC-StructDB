#!/usr/bin/env python3
import sqlite3, sys
from pathlib import Path
db=Path(sys.argv[1] if len(sys.argv)>1 else 'app/data/phrc_bgcstructdb.sqlite')
conn=sqlite3.connect(db)
for table in ['bgc_protein_summary','download_manifest','structure_file_map']:
    print(table, conn.execute(f'select count(*) from {table}').fetchone()[0])
