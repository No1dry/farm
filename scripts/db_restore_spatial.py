"""Explicit administrator restoration of an existing spatial identity, with audit."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store

parser=argparse.ArgumentParser();parser.add_argument('spatial_id');parser.add_argument('--reason',required=True)
parser.add_argument('--db',default='runtime/farm.sqlite3');args=parser.parse_args()
print(json.dumps(Store(args.db).restore_spatial(args.spatial_id,args.reason),ensure_ascii=False))
