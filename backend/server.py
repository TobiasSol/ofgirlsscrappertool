import sqlite3
import time
import random
import re
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from hikerapi import Client

# --- KONFIGURATION ---
API_KEY = "y0a9buus1f3z0vx3gqodr8lh11vvsxyh"
DB_FILE = "instagram_leads.db"
APP_PASSWORD = "Tobideno85!"

app = Flask(__name__)
CORS(app)

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
                  change_details TEXT)''') 
    conn.commit()
    conn.close()

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

                # --- MODUS: SYNC (Updates prüfen) ---
                elif existing and mode == "sync" and existing['status'] != 'hidden':
                    try:
                        details = cl.user_by_username_v1(username)
                        # Wenn wir hier sind, existiert der User noch -> Status OK
                        
                        new_bio = details.get('biography', '')
                        new_followers = details.get('follower_count', 0)
                        new_email = details.get('public_email', '') or extract_email(new_bio)
                        
                        changes = []
                        if new_bio != existing['bio']: changes.append("Bio geändert")
                        old_followers = existing['followers_count'] or 0
                        if abs(new_followers - old_followers) > 10: changes.append(f"Follower: {old_followers}->{new_followers}")

                        new_status = 'changed' if changes else existing['status']
                        # Falls er vorher 'not_found' war und jetzt wieder da ist:
                        if existing['status'] == 'not_found': new_status = 'active' 

                        change_str = ", ".join(changes) if changes else existing['change_details']

                        c.execute('''UPDATE leads SET 
                                     bio=?, email=?, followers_count=?, last_scraped_date=?, status=?, change_details=?
                                     WHERE pk=?''',
                                     (new_bio, new_email, new_followers, datetime.now().isoformat(), new_status, change_str, pk))
                        conn.commit()
                        users_processed += 1
                        JOBS[target_username]['found'] = users_processed
                        JOBS[target_username]['message'] = f'{users_processed} geprüft'

                    except Exception as e:
                        # User existiert wohl nicht mehr oder API Fehler
                        print(f"User {username} nicht gefunden (Sync): {e}")
                        c.execute("UPDATE leads SET status=?, change_details=? WHERE pk=?", 
                                 ('not_found', 'Profil nicht mehr aufrufbar', pk))
                        conn.commit()
            
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

# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    # Passwort-Check deaktiviert für localhost Komfort
    return jsonify({"success": True, "token": "session_valid"})

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
    conn = get_db()
    targets = conn.execute("SELECT username FROM targets").fetchall()
    conn.close()
    
    def run_sync():
        for t in targets:
            scrape_target_logic(t['username'], mode="sync")
            
    threading.Thread(target=run_sync).start()
    return jsonify({"message": "Full Sync gestartet..."})

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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
