#!/usr/bin/env python3
import argparse, csv, hashlib, json, os, sqlite3
from pathlib import Path
from datetime import datetime

PUBLIC_TABLES={
 'MAG_summary.tsv':'mag_summary','BGC_summary.tsv':'bgc_summary','BGC_protein_summary.tsv':'bgc_protein_summary','BiGSCAPE_GCF_summary.tsv':'bigscape_gcf_summary','BiGSCAPE_BGC_to_GCF.tsv':'bigscape_bgc_to_gcf','AF3_model_summary.tsv':'af3_model_summary','Foldseek_besthit_all.tsv':'foldseek_besthit_all','Foldseek_AF3QC_merged_all.tsv':'foldseek_af3qc_merged_all','PHRC_integrated_BGC_protein_structure_summary.tsv':'integrated_summary','column_dictionary.tsv':'column_dictionary'}
SENSITIVE={'drug_discovery_priority_score','priority_class','database_candidate_tier'}
EXCLUDED={'PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv','drug_discovery_ranked_candidates.tsv','candidate_peptides.faa','high_priority_candidate_models.tar.gz'}
ALLOWLIST=[('tables/MAG_summary.tsv','Tables','MAG summary table'),('tables/BGC_summary.tsv','Tables','BGC summary table'),('tables/BGC_protein_summary.tsv','Tables','BGC protein summary table'),('tables/BiGSCAPE_GCF_summary.tsv','Tables','BiG-SCAPE GCF summary table'),('tables/BiGSCAPE_BGC_to_GCF.tsv','Tables','BiG-SCAPE BGC-to-GCF assignments'),('tables/AF3_model_summary.tsv','Tables','AlphaFold3 model summary'),('tables/Foldseek_besthit_all.tsv','Tables','Foldseek best-hit table'),('tables/Foldseek_AF3QC_merged_all.tsv','Tables','Foldseek and AF3 QC merged table'),('tables/PHRC_integrated_BGC_protein_structure_summary.tsv','Tables','Integrated public protein-structure summary'),('tables/column_dictionary.tsv','Documentation','Column dictionary'),('sequences/BGC_proteins.faa','Sequences','BGC protein FASTA'),('antismash/region_gbk.tar.gz','antiSMASH','antiSMASH region GenBank archive'),('antismash/antismash_PRHC_samples.sqsh','antiSMASH','antiSMASH SQLite/squash archive'),('bigscape/gcf_tables.tar.gz','BiG-SCAPE','BiG-SCAPE GCF tables'),('bigscape/networks.tar.gz','BiG-SCAPE','BiG-SCAPE network files'),('bigscape/cytoscape_files.tar.gz','BiG-SCAPE','Cytoscape export archive'),('structures/AF3_final_models_short.tar.gz','Structures','Short AF3 model CIF archive'),('structures/AF3_final_models_medium.tar.gz','Structures','Medium AF3 model CIF archive'),('structures/AF3_final_models_long.tar.gz','Structures','Long AF3 model CIF archive'),('foldseek/Foldseek_besthit_all.tsv.gz','Foldseek','Compressed Foldseek best-hit table'),('foldseek/Foldseek_AF3QC_merged_all.tsv.gz','Foldseek','Compressed Foldseek AF3 QC merged table'),('foldseek/raw_foldseek_outputs.tar.gz','Foldseek','Raw Foldseek output archive'),('docs/README.md','Documentation','Package README'),('docs/data_processing_workflow.md','Documentation','Data processing workflow'),('docs/citation.txt','Documentation','Citation text'),('docs/column_dictionary.tsv','Documentation','Documentation column dictionary'),('checksums/md5sums.txt','Checksums','MD5 checksum manifest')]

def public_id(dataset, value): return f"{dataset}|{value}" if value else ''
def clean_columns(cols): return [c for c in cols if c not in SENSITIVE and 'internal' not in c.lower()]
def create_table(conn, table, cols):
    defs=', '.join([f'"{c}" TEXT' for c in cols])
    conn.execute(f'drop table if exists {table}')
    conn.execute(f'create table {table} ({defs})')
def insert_rows(conn, table, cols, rows):
    qs=','.join(['?']*len(cols)); names=','.join([f'"{c}"' for c in cols])
    conn.executemany(f'insert into {table} ({names}) values ({qs})', ([r.get(c,'') for c in cols] for r in rows))
def load_tsv(path):
    with path.open(newline='') as f:
        reader=csv.DictReader(f, delimiter='	')
        return reader.fieldnames or [], list(reader)
def md5_map(root):
    out={}; p=root/'checksums/md5sums.txt'
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            parts=line.split(None,1)
            if len(parts)==2: out[parts[1].lstrip('./')]=parts[0]
    return out
def add_public_ids(table, cols, rows, dataset):
    extra=['dataset']
    if table=='mag_summary': extra+=['public_mag_id']
    elif table=='bgc_summary': extra+=['public_bgc_id','public_mag_id','public_gcf_id']
    elif table=='bigscape_gcf_summary': extra+=['public_gcf_id']
    elif table in {'bgc_protein_summary','af3_model_summary','foldseek_besthit_all','foldseek_af3qc_merged_all','integrated_summary'}: extra+=['public_protein_id','public_bgc_id','public_mag_id','public_gcf_id','has_structure']
    new=[c for c in extra if c not in cols]+cols
    for r in rows:
        r['dataset']=dataset
        if 'mag_id' in r: r['public_mag_id']=public_id(dataset,r.get('mag_id'))
        if 'genome_id' in r: r['public_mag_id']=public_id(dataset,r.get('genome_id'))
        if 'bgc_id' in r: r['public_bgc_id']=public_id(dataset,r.get('bgc_id'))
        if 'bigscape_gcf_id_full_primary' in r: r['public_gcf_id']=public_id(dataset,r.get('bigscape_gcf_id_full_primary'))
        if 'query' in r: r['public_protein_id']=public_id(dataset,r.get('query'))
        if 'model_cif' in r: r['has_structure']='1' if r.get('model_cif') else '0'
    return new, rows
def build_structure_map(conn, root, dataset):
    conn.execute('drop table if exists structure_file_map')
    conn.execute('create table structure_file_map (public_protein_id TEXT primary key, filename TEXT, relative_path TEXT, length_bucket TEXT, public_safe INTEGER)')
    cifs={p.name:p.relative_to(root).as_posix() for p in (root/'structures').glob('AF3_final_models_*_cif/*.cif')}
    rows=[]
    for name, rel in cifs.items():
        query=name[:-4]; bucket='short' if 'short' in rel else 'medium' if 'medium' in rel else 'long'
        rows.append((public_id(dataset,query),name,rel,bucket,1))
    conn.executemany('insert or replace into structure_file_map values (?,?,?,?,?)', rows)
    return len(rows)
def build_download_manifest(conn, root, dataset):
    checks=md5_map(root)
    conn.execute('drop table if exists download_manifest')
    conn.execute('create table download_manifest (file_key TEXT primary key, filename TEXT, relative_path TEXT, description TEXT, category TEXT, size_bytes INTEGER, compression TEXT, md5 TEXT, version TEXT, modified_date TEXT, public_safe INTEGER)')
    rows=[]
    for rel,cat,desc in ALLOWLIST:
        if any(x in rel for x in EXCLUDED): continue
        p=root/rel
        if not p.exists(): continue
        key=hashlib.sha1(rel.encode()).hexdigest()[:16]
        comp='tar.gz' if rel.endswith('.tar.gz') else 'gzip' if rel.endswith('.gz') else Path(rel).suffix.lstrip('.') or 'none'
        rows.append((key,p.name,rel,desc,cat,p.stat().st_size,comp,checks.get(rel,''),'PHRC_BGCStructDB_v1',datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(),1))
    conn.executemany('insert into download_manifest values (?,?,?,?,?,?,?,?,?,?,?)', rows)
    return len(rows)
def indexes(conn):
    for table in ['mag_summary','bgc_summary','bgc_protein_summary','bigscape_gcf_summary','af3_model_summary','foldseek_besthit_all','download_manifest']:
        for col in ['dataset','public_mag_id','public_bgc_id','public_gcf_id','public_protein_id','query','region_basename','product','gene_name','sequence_length','length_bucket','mean_plddt','af3_confidence_class','compactness_class','target','pdb_structural_match_category','category']:
            try: conn.execute(f'create index if not exists idx_{table}_{col} on {table}("{col}")')
            except sqlite3.OperationalError: pass
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--package-root', required=True); ap.add_argument('--db', required=True); ap.add_argument('--dataset', default='PHRC'); ap.add_argument('--replace', action='store_true')
    args=ap.parse_args(); root=Path(args.package_root); db=Path(args.db); db.parent.mkdir(parents=True, exist_ok=True)
    missing=[name for name in PUBLIC_TABLES if not (root/'tables'/name).exists()]
    if missing: raise SystemExit('Missing required tables: '+', '.join(missing))
    report={'tables':{},'excluded_sensitive_files':sorted([x for x in EXCLUDED if (root/'tables'/x).exists() or (root/x).exists()]),'missing_identifiers':{},'missing_structure_files':0}
    conn=sqlite3.connect(db)
    with conn:
        for filename,table in PUBLIC_TABLES.items():
            cols,rows=load_tsv(root/'tables'/filename); cols=clean_columns(cols); rows=[{k:v for k,v in r.items() if k in cols} for r in rows]
            cols,rows=add_public_ids(table,cols,rows,args.dataset); create_table(conn,table,cols); insert_rows(conn,table,cols,rows)
            report['tables'][table]={'rows':len(rows),'columns':len(cols)}
        report['structure_file_map_rows']=build_structure_map(conn,root,args.dataset)
        report['download_manifest_rows']=build_download_manifest(conn,root,args.dataset)
        conn.execute('drop table if exists database_metadata'); conn.execute('create table database_metadata (key TEXT primary key, value TEXT)')
        conn.executemany('insert into database_metadata values (?,?)', [('version','PHRC_BGCStructDB_v1'),('dataset',args.dataset),('ingested_at',datetime.utcnow().isoformat()+'Z')])
        indexes(conn)
    report_path=db.with_suffix('.ingestion_report.json'); report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
if __name__=='__main__': main()
