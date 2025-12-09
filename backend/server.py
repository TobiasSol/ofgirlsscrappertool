import json
import time
import random
import re
import threading
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from hikerapi import Client

# --- KONFIGURATION ---
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "Tobideno85!")

# JSON Pfad Logik
# Wir nutzen os.path.dirname(__file__), um vom backend/-Ordner aus
# relativ zum Frontend-Datenordner zu navigieren.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Gehe eins hoch (ins Root) und dann nach src/data/users.json
DATA_FILE = os.path.join(BASE_DIR, "..", "src", "data", "users.json")

# Sicherstellen, dass der Ordner existiert
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

# Flask App
app = Flask(__name__, static_folder='../dist', static_url_path='')
CORS(app)

@app.after_request
def set_permissions_policy(response):
    response.headers['Permissions-Policy'] = 'local-network=()'
    return response

JOBS = {}

# --- JSON HELPER ---
def load_data():
    """Lädt die komplette Datenstruktur aus der JSON-Datei."""
    if not os.path.exists(DATA_FILE):
        return {"leads": [], "targets": []}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # MIGRATION: Falls das File nur eine Liste ist (altes Format)
            if isinstance(data, list):
                data = {"leads": data, "targets": []}
            
            # Sicherstellen, dass die Struktur stimmt
            if "leads" not in data: data["leads"] = []
            if "targets" not in data: data["targets"] = []
            
            # Daten-Normalisierung für bestehende Einträge
            for lead in data["leads"]:
                if "followersCount" not in lead: lead["followersCount"] = 0
                if "foundDate" not in lead: lead["foundDate"] = datetime.now().isoformat()
                if "lastScrapedDate" not in lead: lead["lastScrapedDate"] = lead["foundDate"]
                if "changeDetails" not in lead: lead["changeDetails"] = ""
                
            return data
    except Exception as e:
        print(f"Fehler beim Laden der JSON: {e}")
        return {"leads": [], "targets": []}

def save_data(data):
    """Speichert die komplette Datenstruktur in die JSON-Datei."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Fehler beim Speichern der JSON: {e}")

# Initialisiere Datei wenn leer
if not os.path.exists(DATA_FILE):
    save_data({"leads": [], "targets": []})

# --- HIKERAPI & LOGIK ---
def extract_email(text):
    if not text: return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""

def scrape_target_logic(target_username, mode="scan"):
    """
    mode='scan': Nur neue finden
    mode='sync': Auch existierende auf Änderungen prüfen
    """
    global JOBS
    print(f"DEBUG: Starte Scraping fuer: {target_username} (Modus: {mode})")
    
    JOBS[target_username] = {
        'status': 'starting', 
        'found': 0, 
        'message': 'Initialisiere...',
        'start_time': datetime.now().isoformat()
    }

    cl = Client(token=API_KEY)
    
    # Daten einmal laden (Achtung: Bei viel Concurrency könnte das zu Race Conditions führen,
    # für diesen Use Case aber meist ok. Besser wäre Locking.)
    data = load_data()
    leads_map = {lead['pk']: lead for lead in data['leads']}
    
    # 1. Target ID holen
    try:
        print(f"DEBUG: Rufe HikerAPI für {target_username}...") 
        target_info = cl.user_by_username_v1(target_username)
        
        if not target_info:
             raise Exception("Keine Daten von API erhalten")

        target_id = target_info.get('pk')
        if not target_id:
             raise Exception(f"Keine PK gefunden")

        follower_count_total = target_info.get('follower_count', 0)
        JOBS[target_username].update({'status': 'running', 'total_followers': follower_count_total, 'message': 'Lade Follower...'})
    except Exception as e:
        print(f"Target Fehler: {e}")
        JOBS[target_username] = {'status': 'error', 'message': f'Fehler: {str(e)}'}
        return

    # 2. Followings laden
    end_cursor = None
    users_processed = 0
    
    while True:
        try:
            users_list, next_cursor = cl.user_following_chunk_gql(target_id, end_cursor=end_cursor)
            
            if not users_list: break
            
            for user in users_list:
                pk = user.get('pk') or user.get('id')
                username = user.get('username')
                full_name = user.get('full_name', '')
                
                existing = leads_map.get(pk)

                # Wenn Blockiert -> IGNORIEREN
                if existing and existing.get('status') == 'blocked':
                    continue
                
                # --- MODUS: SCAN (Neue finden) ---
                if not existing:
                    try:
                        details = cl.user_by_username_v1(username)
                        bio = details.get('biography', '')
                        email = details.get('public_email', '') or extract_email(bio)
                        followers = details.get('follower_count', 0)
                        is_private = 1 if details.get('is_private') else 0
                        
                        new_lead = {
                            "pk": pk,
                            "id": f"user_{pk}", # Für Frontend ID Konsistenz
                            "username": username,
                            "fullName": full_name,
                            "bio": bio,
                            "email": email,
                            "isPrivate": bool(is_private),
                            "followersCount": followers,
                            "sourceAccount": target_username,
                            "foundDate": datetime.now().isoformat(),
                            "lastScrapedDate": datetime.now().isoformat(),
                            "status": "new",
                            "changeDetails": "",
                            "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={username}"
                        }
                        
                        data['leads'].append(new_lead)
                        leads_map[pk] = new_lead # Cache updaten
                        
                        # Speichern nach jedem Fund (etwas I/O lastig, aber sicherer)
                        save_data(data)
                        
                        users_processed += 1
                        JOBS[target_username]['found'] = users_processed
                        JOBS[target_username]['message'] = f'{users_processed} neue Leads gefunden'
                        
                    except Exception as e:
                        print(f"Fehler bei User Detail {username}: {e}")

                # --- MODUS: SYNC ---
                elif existing and mode == "sync" and existing.get('status') != 'hidden':
                    # Sync Logik direkt hier integrieren oder Hilfsfunktion anpassen
                    updated_lead = sync_single_lead_logic(cl, existing)
                    if updated_lead:
                         # Update in Liste finden und ersetzen
                         for i, l in enumerate(data['leads']):
                             if l['pk'] == pk:
                                 data['leads'][i] = updated_lead
                                 break
                         save_data(data)
                         
                    users_processed += 1
                    JOBS[target_username]['found'] = users_processed
                    JOBS[target_username]['message'] = f'{users_processed} geprüft'
            
            if not next_cursor: break
            end_cursor = next_cursor
            time.sleep(1.5)

        except Exception as e:
            print(f"Scraping Fehler Chunk: {e}")
            break
            
    # Update Target Timestamp
    # Check if target exists
    target_found = False
    for t in data['targets']:
        if t['username'] == target_username:
            t['lastScraped'] = datetime.now().isoformat()
            target_found = True
            break
    
    if not target_found:
        data['targets'].append({
            "username": target_username,
            "lastScraped": datetime.now().isoformat()
        })
        
    save_data(data)
    
    JOBS[target_username]['status'] = 'finished'
    JOBS[target_username]['message'] = 'Fertig!'
    print(f"Fertig mit {target_username}")

def sync_single_lead_logic(client, lead):
    """Prüft einen einzelnen Lead auf Updates und gibt das aktualisierte Objekt zurück (oder None)"""
    username = lead['username']
    try:
        details = client.user_by_username_v1(username)
        if not details: return None

        new_bio = details.get('biography', '')
        new_followers = details.get('follower_count', 0)
        new_email = details.get('public_email', '') or extract_email(new_bio)
        new_external_url = details.get('external_url', '')

        changes = []
        if new_bio != lead.get('bio', ''): changes.append("Bio neu")
        if new_external_url != lead.get('externalUrl', ''): changes.append("Link neu")
        
        old_followers = lead.get('followersCount', 0)
        if abs(new_followers - old_followers) > 10: 
            changes.append(f"Follower: {old_followers}->{new_followers}")

        new_status = lead['status']
        if lead['status'] == 'not_found': new_status = 'active'
        if changes and new_status != 'blocked': new_status = 'changed'

        change_str = ", ".join(changes) if changes else lead.get('changeDetails', '')

        # Objekt aktualisieren
        lead['bio'] = new_bio
        lead['email'] = new_email
        lead['followersCount'] = new_followers
        lead['lastScrapedDate'] = datetime.now().isoformat()
        lead['status'] = new_status
        lead['changeDetails'] = change_str
        lead['externalUrl'] = new_external_url
        lead['fullName'] = details.get('full_name', '')
        
        # Falls sich was geändert hat, Update-Datum setzen
        if changes:
             lead['lastUpdatedDate'] = datetime.now().isoformat()
        
        return lead
    except Exception as e:
        print(f"Fehler Sync {username}: {e}")
        return None

# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get('password') == APP_PASSWORD:
        return jsonify({"success": True, "token": "session_valid"})
    return jsonify({"success": False}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    data = load_data()
    # Sortierung (optional, hier im Backend oder Frontend)
    # data['leads'].sort(key=lambda x: x['foundDate'], reverse=True)
    return jsonify(data)

@app.route('/api/add-target', methods=['POST'])
def add_target():
    username = request.json.get('username')
    if not username: return jsonify({"error": "Missing username"}), 400
    
    # Target sofort in DB/JSON eintragen
    data = load_data()
    if not any(t['username'] == username for t in data['targets']):
        data['targets'].append({"username": username, "lastScraped": None})
        save_data(data)
    
    threading.Thread(target=scrape_target_logic, args=(username, "scan")).start()
    return jsonify({"message": f"Startet...", "job_id": username})

@app.route('/api/sync', methods=['POST'])
def sync_all():
    data = load_data()
    targets = data.get('targets', [])
    
    def run_sync():
        for t in targets:
            scrape_target_logic(t['username'], mode="sync")
            
    threading.Thread(target=run_sync).start()
    return jsonify({"message": "Full Sync gestartet..."})

@app.route('/api/sync-users', methods=['POST'])
def sync_users_endpoint():
    usernames = request.json.get('usernames', [])
    if not usernames: return jsonify({"error": "No usernames"}), 400
    
    job_id = f"sync_{int(time.time())}"
    JOBS[job_id] = {'status': 'running', 'found': 0, 'total': len(usernames), 'message': 'Starte Sync...'}

    def run_sync_job(job_id, users):
        processed = 0
        cl = Client(token=API_KEY)
        
        # Wir laden Daten einmal frisch
        data = load_data()
        
        for u in users:
            # Finde User in leads
            lead = next((l for l in data['leads'] if l['username'] == u), None)
            if lead:
                updated = sync_single_lead_logic(cl, lead)
                if updated:
                    # Muss nicht explizit zurückgeschrieben werden da 'lead' Referenz ist,
                    # aber wir müssen save_data aufrufen
                    save_data(data) 
            
            processed += 1
            JOBS[job_id]['found'] = processed
            JOBS[job_id]['message'] = f'Pruefe {u} ({processed}/{len(users)})'
        
        JOBS[job_id]['status'] = 'finished'
        JOBS[job_id]['message'] = 'Fertig.'

    threading.Thread(target=run_sync_job, args=(job_id, usernames)).start()
    return jsonify({"success": True, "job_id": job_id})

def add_lead_logic(username):
    cl = Client(token=API_KEY)
    try:
        user = cl.user_by_username_v1(username)
        if not user: return
        
        pk = user.get('pk')
        data = load_data()
        
        if any(l['pk'] == pk for l in data['leads']):
            print(f"User {username} existiert schon.")
            return

        bio = user.get('biography', '')
        email = user.get('public_email', '') or extract_email(bio)
        
        new_lead = {
            "pk": pk,
            "id": f"user_{pk}",
            "username": user['username'],
            "fullName": user['full_name'],
            "bio": bio,
            "email": email,
            "isPrivate": bool(user.get('is_private')),
            "followersCount": user.get('follower_count', 0),
            "sourceAccount": 'manually_added',
            "foundDate": datetime.now().isoformat(),
            "lastScrapedDate": datetime.now().isoformat(),
            "status": "new",
            "changeDetails": "",
            "externalUrl": user.get('external_url', ''),
            "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={user['username']}"
        }
        
        data['leads'].append(new_lead)
        save_data(data)
        print(f"Manuell hinzugefuegt: {username}")
        
    except Exception as e:
        print(f"Fehler add_lead: {e}")

@app.route('/api/add-lead', methods=['POST'])
def add_lead():
    username = request.json.get('username')
    if not username: return jsonify({"error": "Missing username"}), 400
    try:
        add_lead_logic(username)
        return jsonify({"message": f"OK", "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mark-exported', methods=['POST'])
def mark_exported():
    usernames = request.json.get('usernames', [])
    if not usernames: return jsonify({"error": "No usernames"}), 400
    
    data = load_data()
    now = datetime.now().isoformat()
    
    count = 0
    for lead in data['leads']:
        if lead['username'] in usernames:
            lead['lastExported'] = now
            count += 1
            
    save_data(data)
    return jsonify({"success": True})

@app.route('/api/import', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        imported_data = json.load(file)
        current_data = load_data()
        
        # Merge Logic
        # Wir nehmen an, dass imported_data entweder eine Liste von Leads ist 
        # oder ein Objekt mit "leads" und "targets".
        
        new_leads = []
        if isinstance(imported_data, list):
            new_leads = imported_data
        elif isinstance(imported_data, dict) and "leads" in imported_data:
            new_leads = imported_data["leads"]
            
            # Merge Targets wenn vorhanden
            if "targets" in imported_data:
                existing_targets = {t['username'] for t in current_data['targets']}
                for t in imported_data['targets']:
                    if t['username'] not in existing_targets:
                        current_data['targets'].append(t)
        
        # Merge Leads
        # Strategie: Existierende Leads werden aktualisiert (wenn PK matcht), neue hinzugefügt.
        # PK ist unique Identifier.
        
        leads_map = {str(l['pk']): l for l in current_data['leads']}
        added_count = 0
        updated_count = 0
        
        for lead in new_leads:
            pk = str(lead.get('pk'))
            if not pk: continue
            
            # Normalisierung Import-Daten
            if "followersCount" not in lead: lead["followersCount"] = lead.get("followers_count", 0)
            if "foundDate" not in lead: lead["foundDate"] = lead.get("found_date", datetime.now().isoformat())
            # ... weitere Felder bei Bedarf mappen
            
            if pk in leads_map:
                # Update existierenden Lead (optional: nur wenn Import neuer ist? Hier: Überschreiben)
                # Wir behalten den Status bei, es sei denn der Import hat was Spezifisches?
                # Einfachheitshalber: Wir mergen Felder.
                existing = leads_map[pk]
                existing.update(lead) # Import gewinnt
                updated_count += 1
            else:
                current_data['leads'].append(lead)
                leads_map[pk] = lead
                added_count += 1
                
        save_data(current_data)
        return jsonify({"success": True, "added": added_count, "updated": updated_count})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_data():
    if not os.path.exists(DATA_FILE):
        return jsonify({"error": "No data found"}), 404
    return send_from_directory(os.path.dirname(DATA_FILE), os.path.basename(DATA_FILE), as_attachment=True)

@app.route('/api/delete-users', methods=['POST'])
def delete_users():
    pks = request.json.get('pks', []) # Erwartet Array von IDs (PKs als Integer oder Strings)
    if not pks: return jsonify({"error": "No IDs"}), 400
    
    # Stelle sicher dass Vergleichstypen passen (PKs in JSON sind meist Int, vom Frontend evtl String?)
    # Wir casten sicherheitshalber zu String für den Vergleich, wenn PK im JSON Int ist.
    # Aber besser: Wir schauen was im JSON steht. Meist Int.
    
    data = load_data()
    initial_len = len(data['leads'])
    
    # Filter: Behalte nur Leads, deren PK NICHT in der Lösch-Liste ist
    data['leads'] = [l for l in data['leads'] if l['pk'] not in pks and str(l['pk']) not in [str(p) for p in pks]]
    
    deleted_count = initial_len - len(data['leads'])
    save_data(data)
    
    return jsonify({"success": True, "deleted": deleted_count})

@app.route('/api/job-status/<username>', methods=['GET'])
def job_status(username):
    job = JOBS.get(username)
    if not job:
        return jsonify({'status': 'not_found'})
    return jsonify(job)

@app.route('/api/lead/update-status', methods=['POST'])
def update_status():
    data_in = request.json
    pk = data_in.get('pk')
    status = data_in.get('status')
    
    data = load_data()
    found = False
    for lead in data['leads']:
        if lead['pk'] == pk or str(lead['pk']) == str(pk):
            lead['status'] = status
            found = True
            break
            
    if found:
        save_data(data)
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

# Catch-All Route für React Router (muss nach allen API-Routen kommen)
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # Wenn es eine API-Route ist, 404 zurückgeben
    if path.startswith('api/'):
        return jsonify({"error": "Not found"}), 404
    
    # Statische Dateien (JS, CSS, etc.) servieren
    if path and path != 'index.html':
        try:
            return send_from_directory(app.static_folder, path)
        except:
            pass
    
    # Alle anderen Routen -> index.html (für React Router)
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception as e:
        return f"Frontend not built yet. Error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
