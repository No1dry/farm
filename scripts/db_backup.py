import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');parser.add_argument('--db',default='runtime/farm.sqlite3')
    args=parser.parse_args()
    if not Path(args.db).is_file():raise SystemExit('Source database does not exist')
    if Path(args.destination).exists():raise SystemExit('Choose a new backup path; existing backups are not overwritten')
    print(Store(args.db).backup(args.destination))
