import sqlite3
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / 'PHRC_BGCStructDB_v1'

def test_ingestion_builds_public_tables(tmp_path):
    db=tmp_path/'test.sqlite'
    subprocess.run([sys.executable,'scripts/ingest_package_to_sqlite.py','--package-root',str(PACKAGE),'--db',str(db)], check=True)
    conn=sqlite3.connect(db)
    assert conn.execute('select count(*) from bgc_protein_summary').fetchone()[0] == 22626
    cols=[r[1] for r in conn.execute('pragma table_info(integrated_summary)')]
    assert 'drug_discovery_priority_score' not in cols
    names={r[0] for r in conn.execute('select filename from download_manifest')}
    assert 'PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv' not in names
    assert conn.execute('select count(*) from structure_file_map').fetchone()[0] >= 10972
