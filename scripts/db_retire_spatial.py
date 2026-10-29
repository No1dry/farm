"""Explicit, audited retirement of a superseded manifest-only spatial identity."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('spatial_id');parser.add_argument('--reason',required=True)
    parser.add_argument('--db',default='runtime/farm.sqlite3');args=parser.parse_args()
    if not Path(args.db).is_file():raise SystemExit('Database does not exist')
    print(json.dumps(Store(args.db).retire_spatial(args.spatial_id,args.reason),ensure_ascii=False))
