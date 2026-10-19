"""Queue overdue alerts; add --send to deliver pending mail through configured SMTP."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.assets import AssetRegistry
from app.notifications import deliver_pending, queue_overdue, smtp_config

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send', action='store_true', help='Deliver mail through SMTP; without this flag only queue overdue notices')
    parser.add_argument('--limit', type=int, default=50, help='Maximum pending notices to deliver (1–500)')
    parser.add_argument('--recover-processing', action='store_true', help='Reset interrupted claims to pending after stopping all workers; may duplicate already-accepted mail')
    args = parser.parse_args()
    if not 1 <= args.limit <= 500:
        parser.error('--limit must be between 1 and 500')
    registry = AssetRegistry(os.environ.get('SIAS_DATABASE_PATH', str(Path(__file__).resolve().parents[1] / 'instance' / 'sias.sqlite3')))
    if args.recover_processing:
        with registry.connect() as db:
            cursor = db.execute("UPDATE notifications SET status='pending', last_error='Operator recovered interrupted delivery; previous SMTP outcome unknown' WHERE status='processing'")
            print('Recovered interrupted deliveries:', cursor.rowcount)
    print('Queued overdue alerts:', queue_overdue(registry))
    if args.send:
        try:
            config = smtp_config()
        except ValueError as error:
            sys.exit(str(error))
        result = deliver_pending(registry, config, args.limit)
        print('Delivery results:', result)
        if result['failed']:
            sys.exit(1)
