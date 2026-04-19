"""
Einmalige Migration: kopiert alle Daten aus der lokalen SQLite (lokal.db)
in die Cloud-Postgres (Neon), die in der .env als DATABASE_URL hinterlegt ist.

Verwendung:
    python migrate_sqlite_to_postgres.py

Eigenschaften:
- Liest direkt aus 'lokal.db' im Projekt-Root
- Schreibt in die DB hinter DATABASE_URL (Postgres)
- Idempotent: existierende Eintraege werden uebersprungen, keine Duplikate
- Batch-Commit alle 1000 Zeilen, schonend mit Speicher und Neon-Compute
"""

import os
import sys
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Backend-Pfad einbinden, damit wir die SQLAlchemy-Modelle wiederverwenden
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# WICHTIG: Backend importiert .env und prueft DATABASE_URL beim Import
from backend.server import app, db, Lead, Target  # noqa: E402


SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lokal.db')


def fetch_all(conn, table):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main():
    if not os.path.exists(SQLITE_PATH):
        sys.exit(f"❌ {SQLITE_PATH} nicht gefunden – nichts zu migrieren.")

    print(f"📂 Lese SQLite: {SQLITE_PATH}")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    targets_rows = fetch_all(sqlite_conn, "targets")
    leads_rows = fetch_all(sqlite_conn, "leads")
    sqlite_conn.close()

    print(f"📊 Quelle: {len(targets_rows)} Targets, {len(leads_rows)} Leads")

    with app.app_context():
        print("🔧 Stelle sicher, dass alle Tabellen in Postgres existieren...")
        db.create_all()

        print("🔍 Lese existierende Datensaetze in Postgres...")
        existing_target_names = {t.username for t in Target.query.all()}
        existing_lead_pks = {row[0] for row in db.session.query(Lead.pk).all()}
        print(f"   > {len(existing_target_names)} Targets, {len(existing_lead_pks)} Leads schon vorhanden")

        # Targets uebertragen
        added_targets = 0
        for t in targets_rows:
            if t['username'] not in existing_target_names:
                db.session.add(Target(
                    username=t['username'],
                    last_scraped=t.get('last_scraped'),
                ))
                added_targets += 1
        db.session.commit()
        print(f"✅ {added_targets} neue Targets uebertragen")

        # Leads uebertragen (mit Batch-Commits)
        added_leads = 0
        skipped = 0
        batch_size = 1000

        print(f"🚀 Starte Lead-Migration ({len(leads_rows)} Quell-Eintraege)...")
        for i, l in enumerate(leads_rows, start=1):
            pk = l.get('pk')
            if not pk:
                skipped += 1
                continue
            if pk in existing_lead_pks:
                skipped += 1
                continue

            db.session.add(Lead(
                pk=pk,
                username=l.get('username'),
                full_name=l.get('full_name'),
                bio=l.get('bio'),
                email=l.get('email'),
                is_private=bool(l.get('is_private')) if l.get('is_private') is not None else False,
                followers_count=l.get('followers_count') or 0,
                source_account=l.get('source_account'),
                found_date=l.get('found_date'),
                last_scraped_date=l.get('last_scraped_date'),
                status=l.get('status') or 'new',
                change_details=l.get('change_details') or '',
                avatar=l.get('avatar'),
                external_url=l.get('external_url'),
                last_updated_date=l.get('last_updated_date'),
                last_exported=l.get('last_exported'),
                is_german=l.get('is_german'),
                german_check_result=l.get('german_check_result'),
            ))
            existing_lead_pks.add(pk)
            added_leads += 1

            if added_leads and added_leads % batch_size == 0:
                db.session.commit()
                print(f"   > {i}/{len(leads_rows)} verarbeitet, {added_leads} neu")

        db.session.commit()
        print()
        print("=" * 50)
        print(f"✅ FERTIG")
        print(f"   Targets neu: {added_targets}")
        print(f"   Leads neu:   {added_leads}")
        print(f"   uebersprungen (Duplikate/leer): {skipped}")
        print("=" * 50)


if __name__ == "__main__":
    main()
