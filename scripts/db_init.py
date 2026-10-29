"""Initialize or idempotently refresh the local database from reviewed sources."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.importer import initialize
from backend.reporting import export_mappings
from scripts.release_data_seed import bootstrap_database


def initialize_database(path, *, release_seed=True):
    """Preserve published UUIDs on first install, then refresh sources idempotently."""
    path=Path(path)
    bootstrapped=bootstrap_database(path) if release_seed else False
    return initialize(path),bootstrapped

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',default='runtime/farm.sqlite3')
    parser.add_argument('--without-release-seed',action='store_true',help='Create independent UUIDs when initializing a new database')
    args=parser.parse_args();store,bootstrapped=initialize_database(Path(args.db),release_seed=not args.without_release_seed)
    export_mappings(store,Path('data/audit'))
    print(json.dumps({**{dataset:store.summary(dataset)['entity_count'] for dataset in ('real','demo')},'release_seed_initialized':bootstrapped},ensure_ascii=False))
