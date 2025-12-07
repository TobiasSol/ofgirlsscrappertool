import sqlite3
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
# Flexibel für Replit, Render und Lokal
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "Tobideno85!")

# Datenbank Pfad Logik
# Auf Render setzen wir DATA_PATH per Env Var auf '/data' (für Persistent Disk)
# Auf Replit/Lokal ist DATA_PATH leer, also nutzen wir '.' (aktueller Ordner)
DATA_PATH = os.environ.get("DATA_PATH", ".")
DB_FILE = os.path.join(DATA_PATH, "instagram_leads.db")

# Sicherstellen, dass der Ordner existiert
if DATA_PATH != "." and not os.path.exists(DATA_PATH):
    os.makedirs(DATA_PATH, exist_ok=True)

# Flask App mit statischen Dateien für Production
app = Flask(__name__, static_folder='../dist', static_url_path='')
CORS(app)

# After-Request Handler: Setze Permissions-Policy für alle Responses
@app.after_request
def set_permissions_policy(response):
    # Blockiere lokale Netzwerk-Zugriffe
    response.headers['Permissions-Policy'] = 'local-network=()'
    return response

# Globaler Status-Speicher für laufende Jobs
# Format: {'username': {'status': 'running', 'found': 0, 'total_followers': 0, 'message': '...'}}
JOBS = {}

# --- DATENBANK HELPER ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS targets 
                 (username TEXT PRIMARY KEY, last_scraped TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (pk INTEGER PRIMARY KEY, 
                  username TEXT, 
                  full_name TEXT, 
                  bio TEXT, 
                  email TEXT, 
                  is_private INTEGER, 
                  followers_count INTEGER,
                  source_account TEXT, 
                  found_date TEXT, 
                  last_scraped_date TEXT,
                  status TEXT,
                  change_details TEXT,
                  last_exported TEXT)''') 
    conn.commit()
    conn.close()

# Datenbank beim Import initialisieren (auch für Gunicorn)
init_db()

# --- HIKERAPI & LOGIK ---
def extract_email(text):
    if not text: return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""

def scrape_target_logic(target_username, mode="scan"):
    """
    mode='scan': Nur neue finden
    mode='sync': Auch existierende auf Änderungen prüfen (für TARGETS)
    """
    global JOBS
    print(f"🚀 Starte Scraping für: {target_username} (Modus: {mode})")
    
    JOBS[target_username] = {
        'status': 'starting', 
        'found': 0, 
        'message': 'Initialisiere...',
        'start_time': datetime.now().isoformat()
    }

    cl = Client(token=API_KEY)
    conn = get_db()
    c = conn.cursor()
    
    # 1. Target ID holen
    try:
        target_info = cl.user_by_username_v1(target_username)
        target_id = target_info['pk']
        follower_count_total = target_info.get('follower_count', 0)
        JOBS[target_username].update({'status': 'running', 'total_followers': follower_count_total, 'message': 'Lade Follower...'})
    except Exception as e:
        print(f"❌ Target nicht gefunden: {e}")
        JOBS[target_username] = {'status': 'error', 'message': f'Target nicht gefunden: {str(e)}'}
        return

    # 2. Followings laden (GQL Chunk)
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
                
                # Check DB
                c.execute("SELECT * FROM leads WHERE pk=?", (pk,))
                existing = c.fetchone()

                # Wenn Blockiert -> IGNORIEREN
                if existing and existing['status'] == 'blocked':
                    continue
                
                # --- MODUS: SCAN (Neue finden) ---
                if not existing:
                    # Details holen
                    try:
                        details = cl.user_by_username_v1(username)
                        bio = details.get('biography', '')
                        email = details.get('public_email', '') or extract_email(bio)
                        followers = details.get('follower_count', 0)
                        is_private = 1 if details.get('is_private') else 0
                        
                        c.execute('''INSERT INTO leads 
                                     (pk, username, full_name, bio, email, is_private, followers_count, source_account, found_date, last_scraped_date, status, change_details)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                     (pk, username, full_name, bio, email, is_private, followers, target_username, datetime.now().isoformat(), datetime.now().isoformat(), 'new', ''))
                        conn.commit()
                        users_processed += 1
                        # Update Job Status
                        JOBS[target_username]['found'] = users_processed
                        JOBS[target_username]['message'] = f'{users_processed} neue Leads gefunden'
                        
                    except Exception as e:
                        print(f"Fehler bei User Detail {username}: {e}")

                # --- MODUS: SYNC (Updates prüfen - nur wenn autom. Sync läuft) ---
                elif existing and mode == "sync" and existing['status'] != 'hidden':
                    sync_single_lead(cl, c, existing)
                    conn.commit()
                    users_processed += 1
                    JOBS[target_username]['found'] = users_processed
                    JOBS[target_username]['message'] = f'{users_processed} geprüft'
            
            if not next_cursor: break
            end_cursor = next_cursor
            time.sleep(1.5)

        except Exception as e:
            print(f"Scraping Fehler Chunk: {e}")
            break
            
    # Update Target Timestamp & Job Finish
    c.execute("INSERT OR REPLACE INTO targets (username, last_scraped) VALUES (?, ?)", 
              (target_username, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    JOBS[target_username]['status'] = 'finished'
    JOBS[target_username]['message'] = 'Fertig!'
    print(f"✅ Fertig mit {target_username}")

def sync_single_lead(client, cursor, existing_row):
    """Prüft einen einzelnen Lead auf Updates"""
    username = existing_row['username']
    pk = existing_row['pk']
    try:
        # FIX: Wir nutzen ZWINGEND user_by_username_v1, da user_by_id_v1 oft veraltete Daten liefert.
        # Das entspricht exakt der Logik beim "Neu Hinzufügen".
        details = client.user_by_username_v1(username)
        
        if not details:
            print(f"Keine Details für {username} gefunden.")
            return False

        new_bio = details.get('biography', '')
        new_followers = details.get('follower_count', 0)
        new_email = details.get('public_email', '') or extract_email(new_bio)
        new_external_url = details.get('external_url', '')

        # DEBUG PRINTS
        print(f"--- Sync: {username} ---")
        print(f"OLD Bio: {existing_row['bio']}")
        print(f"NEW Bio: {new_bio}")
        print(f"NEW Url: {new_external_url}")
        
        changes = []
        # Update erzwingen, auch wenn gleich
        if new_bio != existing_row['bio']: 
            changes.append("Bio neu")
        
        if new_external_url != existing_row['external_url']:
            changes.append("Link neu")

        old_followers = existing_row['followers_count'] or 0
        if abs(new_followers - old_followers) > 10: 
            changes.append(f"Follower: {old_followers}->{new_followers}")

        new_status = existing_row['status']
        if existing_row['status'] == 'not_found': new_status = 'active'
        if changes and new_status != 'blocked': new_status = 'changed'

        change_str = ", ".join(changes) if changes else existing_row['change_details']

        cursor.execute('''UPDATE leads SET 
                        bio=?, email=?, followers_count=?, last_scraped_date=?, status=?, change_details=?, external_url=?, full_name=?
                        WHERE pk=?''',
                        (new_bio, new_email, new_followers, datetime.now().isoformat(), new_status, change_str, new_external_url, details.get('full_name', ''), pk))
        
        return True
    except Exception as e:
        print(f"Fehler bei {username}: {e}")
        return False

def sync_specific_users_logic(usernames):
    print(f"🔄 Starte Sync für {len(usernames)} User...")
    cl = Client(token=API_KEY)
    conn = get_db()
    c = conn.cursor()
    
    for username in usernames:
        c.execute("SELECT * FROM leads WHERE username=?", (username,))
        row = c.fetchone()
        if row:
            sync_single_lead(cl, c, row)
            conn.commit()
    
    conn.close()
    print("✅ Sync fertig.")

# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get('password') == APP_PASSWORD:
        return jsonify({"success": True, "token": "session_valid"})
    return jsonify({"success": False}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads ORDER BY found_date DESC").fetchall()
    targets = conn.execute("SELECT * FROM targets").fetchall()
    conn.close()
    return jsonify({
        "leads": [dict(row) for row in leads],
        "targets": [dict(row) for row in targets]
    })

@app.route('/api/add-target', methods=['POST'])
def add_target():
    username = request.json.get('username')
    if not username: return jsonify({"error": "Missing username"}), 400
    
    threading.Thread(target=scrape_target_logic, args=(username, "scan")).start()
    return jsonify({"message": f"Startet...", "job_id": username})

@app.route('/api/sync', methods=['POST'])
def sync_all():
    # Sync Targets (Standard)
    conn = get_db()
    targets = conn.execute("SELECT username FROM targets").fetchall()
    conn.close()
    
    def run_sync():
        for t in targets:
            scrape_target_logic(t['username'], mode="sync")
            
    threading.Thread(target=run_sync).start()
    return jsonify({"message": "Full Sync gestartet..."})

@app.route('/api/sync-users', methods=['POST'])
def sync_users_endpoint():
    usernames = request.json.get('usernames', [])
    if not usernames: return jsonify({"error": "No usernames"}), 400
    
    # Job ID erstellen (z.B. "sync_12345")
    job_id = f"sync_{int(time.time())}"
    
    # Job initialisieren
    JOBS[job_id] = {
        'status': 'running',
        'found': 0,
        'total': len(usernames),
        'message': 'Starte Sync...'
    }

    def run_sync_job(job_id, users):
        processed = 0
        cl = Client(token=API_KEY)
        conn = get_db()
        c = conn.cursor()
        
        for u in users:
            c.execute("SELECT * FROM leads WHERE username=?", (u,))
            row = c.fetchone()
            if row:
                sync_single_lead(cl, c, row)
                conn.commit()
            processed += 1
            JOBS[job_id]['found'] = processed
            JOBS[job_id]['message'] = f'Pruefe {u} ({processed}/{len(users)})'
        
        conn.close()
        JOBS[job_id]['status'] = 'finished'
        JOBS[job_id]['message'] = 'Fertig.'

    threading.Thread(target=run_sync_job, args=(job_id, usernames)).start()
    
    return jsonify({"success": True, "job_id": job_id})

def add_lead_logic(username):
    print(f"Versuche manuell hinzuzufuegen: {username}")
    cl = Client(token=API_KEY)
    conn = get_db()
    c = conn.cursor()
    try:
        user = cl.user_by_username_v1(username)
        if not user:
            print(f"User {username} nicht auf Instagram gefunden.")
            return

        pk = user.get('pk')
        
        c.execute("SELECT pk FROM leads WHERE pk=?", (pk,))
        if not c.fetchone():
            bio = user.get('biography', '')
            email = user.get('public_email', '') or extract_email(bio)
            followers = user.get('follower_count', 0)
            is_private = 1 if user.get('is_private') else 0
            external_url = user.get('external_url', '')

            c.execute('''INSERT INTO leads 
                            (pk, username, full_name, bio, email, is_private, followers_count, source_account, found_date, last_scraped_date, status, change_details, external_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (pk, user['username'], user['full_name'], bio, email, is_private, followers, 'manually_added', datetime.now().isoformat(), datetime.now().isoformat(), 'new', '', external_url))
            conn.commit()
            print(f"Manuell hinzugefuegt: {username}")
        else:
            print(f"User {username} existiert schon in der DB.")
    except Exception as e:
        print(f"Fehler beim manuellen Hinzufuegen von {username}: {e}")
    finally:
        conn.close()

@app.route('/api/add-lead', methods=['POST'])
def add_lead():
    username = request.json.get('username')
    if not username: return jsonify({"error": "Missing username"}), 400
    
    # Synchron ausführen für direktes Feedback
    try:
        add_lead_logic(username)
        return jsonify({"message": f"{username} wurde hinzugefügt (oder existierte bereits).", "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mark-exported', methods=['POST'])
def mark_exported():
    usernames = request.json.get('usernames', [])
    if not usernames: return jsonify({"error": "No usernames"}), 400
    
    conn = get_db()
    now = datetime.now().isoformat()
    # Nutze executemany für Performance
    conn.executemany("UPDATE leads SET last_exported=? WHERE username=?", [(now, u) for u in usernames])
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/delete-users', methods=['POST'])
def delete_users():
    pks = request.json.get('pks', [])
    if not pks: return jsonify({"error": "No IDs"}), 400
    
    conn = get_db()
    # Erstelle Platzhalter String (?,?,?)
    placeholders = ','.join('?' * len(pks))
    sql = f"DELETE FROM leads WHERE pk IN ({placeholders})"
    conn.execute(sql, pks)
    conn.commit()
    conn.close()
    return jsonify({"success": True, "deleted": len(pks)})

@app.route('/api/job-status/<username>', methods=['GET'])
def job_status(username):
    job = JOBS.get(username)
    if not job:
        return jsonify({'status': 'not_found'})
    return jsonify(job)

@app.route('/api/lead/update-status', methods=['POST'])
def update_status():
    data = request.json
    pk = data.get('pk')
    status = data.get('status')
    conn = get_db()
    conn.execute("UPDATE leads SET status=? WHERE pk=?", (status, pk))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# Catch-All Route für React Router (muss nach allen API-Routen kommen)
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
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
