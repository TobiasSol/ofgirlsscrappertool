import json
import os
import sys
from datetime import datetime

# Pfad zum Backend hinzufügen, damit wir die Datenbank-Modelle nutzen können
sys.path.append(os.getcwd())

from backend.server import app, db, Lead, Target

def manual_import():
    json_path = os.path.join(os.getcwd(), 'export_temp.json')
    
    if not os.path.exists(json_path):
        print(f"❌ FEHLER: Datei {json_path} nicht gefunden!")
        return

    print(f"📂 Lese Datei: {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    leads_data = data.get('leads', [])
    targets_data = data.get('targets', [])
    
    print(f"📊 Gefunden: {len(leads_data)} Leads und {len(targets_data)} Targets.")

    with app.app_context():
        # 1. Targets importieren
        print("📥 Importiere Targets...")
        for t in targets_data:
            if not Target.query.filter_by(username=t['username']).first():
                db.session.add(Target(username=t['username'], last_scraped=t.get('lastScraped')))
        
        # 2. Leads importieren (High Performance)
        print("🔍 Prüfe existierende User in der Datenbank...")
        existing_pks = {row[0] for row in db.session.query(Lead.pk).all()}
        
        added = 0
        batch_size = 1000
        
        print(f"🚀 Starte Massen-Import von {len(leads_data)} potenziellen Usern...")
        for i, l in enumerate(leads_data):
            pk = l.get('pk')
            if pk and pk not in existing_pks:
                new_lead = Lead(
                    pk=pk,
                    username=l.get('username'),
                    full_name=l.get('fullName'),
                    bio=l.get('bio'),
                    email=l.get('email'),
                    is_private=l.get('isPrivate', False),
                    followers_count=l.get('followersCount', 0),
                    source_account=l.get('sourceAccount'),
                    found_date=l.get('foundDate'),
                    last_scraped_date=l.get('lastScrapedDate'),
                    status=l.get('status', 'new'),
                    change_details=l.get('changeDetails', ''),
                    avatar=l.get('avatar'),
                    external_url=l.get('externalUrl'),
                    last_updated_date=l.get('lastUpdatedDate'),
                    last_exported=l.get('lastExported'),
                    is_german=l.get('isGerman'),
                    german_check_result=l.get('germanCheckResult')
                )
                db.session.add(new_lead)
                added += 1
                existing_pks.add(pk)
            
            # Alle 1000 User einen Zwischenspeicher machen
            if added > 0 and added % batch_size == 0:
                db.session.flush()
                print(f"   > {i+1}/{len(leads_data)} verarbeitet ({added} neu hinzugefügt)...")

        db.session.commit()
        print(f"\n✅ FERTIG! {added} neue User wurden in die Datenbank importiert.")

if __name__ == "__main__":
    manual_import()
