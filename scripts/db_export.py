import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store
from backend.reporting import export_mappings

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',default='runtime/farm.sqlite3');parser.add_argument('--output',default='data/audit')
    args=parser.parse_args()
    if not Path(args.db).is_file():raise SystemExit('Database does not exist; initialize or restore it first')
    print(json.dumps(export_mappings(Store(args.db),args.output),ensure_ascii=False))
