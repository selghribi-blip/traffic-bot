#!/usr/bin/env python3
"""
Export MongoDB traffic_bot data to CSV/Excel reports.
"""
import os
import sys
import csv
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def _sanitize_uri(uri):
    uri = str(uri).strip()
    if (uri.startswith('"') and uri.endswith('"')) or \
       (uri.startswith("'") and uri.endswith("'")):
        uri = uri[1:-1]
    return ''.join(uri.split())


def export_collection(db, collection_name, output_dir, days=None):
    """Export one collection to CSV."""
    col = db[collection_name]
    query = {}
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = {'timestamp': {'$gte': cutoff}}

    cursor = col.find(query).sort('timestamp', -1)
    docs = list(cursor)

    if not docs:
        print(f"  {collection_name}: no documents")
        return 0

    # Flatten and remove _id
    rows = []
    for doc in docs:
        doc.pop('_id', None)
        for k, v in list(doc.items()):
            if isinstance(v, datetime):
                doc[k] = v.isoformat()
            elif isinstance(v, dict):
                doc[k] = str(v)
            elif isinstance(v, list):
                doc[k] = ','.join(str(x) for x in v)
        rows.append(doc)

    # Collect all keys
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    fieldnames = sorted(all_keys)

    filepath = os.path.join(output_dir, f'{collection_name}.csv')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in fieldnames})

    print(f"  {collection_name}: {len(rows)} rows -> {filepath}")
    return len(rows)


def export_excel(db, output_dir, days=7):
    """Export all collections to a single Excel file with sheets."""
    if not HAS_PANDAS:
        print("  pandas not installed - skipping Excel export")
        return

    filepath = os.path.join(output_dir, 'traffic_bot_report.xlsx')
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Visits
        visits = list(db.visits.find({'timestamp': {'$gte': cutoff}})
                      .sort('timestamp', -1).limit(10000))
        if visits:
            for v in visits:
                v.pop('_id', None)
            pd.DataFrame(visits).to_excel(writer, sheet_name='visits', index=False)

        # Ad clicks
        ads = list(db.ad_clicks.find({'timestamp': {'$gte': cutoff}})
                   .sort('timestamp', -1).limit(10000))
        if ads:
            for a in ads:
                a.pop('_id', None)
            pd.DataFrame(ads).to_excel(writer, sheet_name='ad_clicks', index=False)

        # Sessions
        sessions = list(db.sessions.find({'timestamp': {'$gte': cutoff}})
                        .sort('timestamp', -1))
        if sessions:
            for s in sessions:
                s.pop('_id', None)
                for k, v in list(s.items()):
                    if isinstance(v, dict):
                        s[k] = str(v)
            pd.DataFrame(sessions).to_excel(writer, sheet_name='sessions', index=False)

        # Daily stats
        daily = list(db.stats_daily.find().sort('date', -1).limit(365))
        if daily:
            for d in daily:
                d.pop('_id', None)
            pd.DataFrame(daily).to_excel(writer, sheet_name='stats_daily', index=False)

    print(f"  Excel: {filepath}")


def main():
    uri = _sanitize_uri(os.environ.get('MONGODB_URI', ''))
    if not uri:
        print("MONGODB_URI not set")
        sys.exit(1)

    days = int(os.environ.get('EXPORT_DAYS', '7'))
    output_dir = os.environ.get('EXPORT_DIR', './exports')
    os.makedirs(output_dir, exist_ok=True)

    print(f"Connecting to MongoDB...")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client['traffic_bot']

    print(f"Exporting last {days} days to {output_dir}/")
    collections = ['visits', 'ad_clicks', 'form_submits', 'sessions',
                   'stats_hourly', 'stats_daily', 'errors']

    total = 0
    for col in collections:
        total += export_collection(db, col, output_dir, days=days)

    print(f"\nTotal documents exported: {total}")

    # Excel summary
    if HAS_PANDAS:
        export_excel(db, output_dir, days=days)

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Visits (7d):      {db.visits.count_documents({'timestamp': {'$gte': datetime.now(timezone.utc) - timedelta(days=7)}})}")
    print(f"Ad clicks (7d):   {db.ad_clicks.count_documents({'timestamp': {'$gte': datetime.now(timezone.utc) - timedelta(days=7)}})}")
    print(f"Sessions (7d):    {db.sessions.count_documents({'timestamp': {'$gte': datetime.now(timezone.utc) - timedelta(days=7)}})}")
    print(f"Total DB size:    {db.command('dbstats')['dataSize'] / 1024 / 1024:.2f} MB")

    client.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
