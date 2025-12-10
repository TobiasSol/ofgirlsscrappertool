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
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# --- KONFIGURATION ---
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "Tobideno85!")

# Flask App Setup
app = Flask(__name__, static_folder='../dist', static_url_path='')
CORS(app)

# --- DATENBANK KONFIGURATION (NEU) ---
# Nutzt die Replit Datenbank URL oder fällt auf SQLite zurück (für lokale Tests)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

# --- DATENBANK MODELLE ---

class Target(db.Model):
    __tablename__ = 'targets'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    last_scraped = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "username": self.username,
            "lastScraped": self.last_scraped
        }

class Lead(db.Model):
    __tablename__ = 'leads'
    pk = db.Column(db.BigInteger, primary_key=True)  # Instagram ID als Primary Key
    username = db.Column(db.String, nullable=False)
    full_name = db.Column(db.String, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    email = db.Column(db.String, nullable=True)
    is_private = db.Column(db.Boolean, default=False)
    followers_count = db.Column(db.Integer, default=0)
    source_account = db.Column(db.String, nullable=True)
    found_date = db.Column(db.String, nullable=True)
    last_scraped_date = db.Column(db.String, nullable=True)
    status = db.Column(db.String, default="new")
    change_details = db.Column(db.Text, default="")
    avatar = db.Column(db.String, nullable=True)
    external_url = db.Column(db.String, nullable=True)
    last_updated_date = db.Column(db.String, nullable=True)
    last_exported = db.Column(db.String, nullable=True)

    def to_dict(self):
        # Wandelt DB-Objekt in das Format um, das dein Frontend erwartet
        return {
            "pk": self.pk,
            "id": f"user_{self.pk}",
            "username": self.username,
            "fullName": self.full_name,
            "bio": self.bio,
            "email": self.email,
            "isPrivate": self.is_private,
            "followersCount": self.followers_count,
            "sourceAccount": self.source_account,
            "foundDate": self.found_date,
            "lastScrapedDate": self.last_scraped_date,
            "status": self.status,
            "changeDetails": self.change_details,
            "avatar": self.avatar,
            "externalUrl": self.external_url,
            "lastUpdatedDate": self.last_updated_date,
            "lastExported": self.last_exported
        }

# Tabellen erstellen, falls sie noch nicht existieren
# ACHTUNG: Das hier nur ausfuehren, wenn man sicher ist oder lokal.
# Im Deployment kann das den Start blockieren (Timeout), wenn die DB langsam ist.
def init_db_if_needed():
    with app.app_context():
        try:
            db.create_all()
            print("Datenbank Tabellen initialisiert.")
        except Exception as e:
            print(f"Fehler bei DB Initialisierung: {e}")

@app.after_request
def set_permissions_policy(response):
    response.headers['Permissions-Policy'] = 'local-network=()'
    return response

JOBS = {}

# --- HELPER FUNKTIONEN (Angepasst für DB) ---

def extract_email(text):
    if not text: return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""

# --- HIKERAPI & LOGIK ---

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

    # Wir brauchen einen Application Context für DB Operationen im Thread
    with app.app_context():
        cl = Client(token=API_KEY)
        
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
                    pk = int(user.get('pk') or user.get('id'))
                    username = user.get('username')
                    full_name = user.get('full_name', '')
                    
                    # Prüfen ob Lead schon existiert
                    existing_lead = db.session.get(Lead, pk)

                    # Wenn Blockiert -> IGNORIEREN
                    if existing_lead and existing_lead.status == 'blocked':
                        continue
                    
                    # --- MODUS: SCAN (Neue finden) ---
                    if not existing_lead:
                        try:
                            details = cl.user_by_username_v1(username)
                            bio = details.get('biography', '')
                            email = details.get('public_email', '') or extract_email(bio)
                            followers = details.get('follower_count', 0)
                            is_private = True if details.get('is_private') else False
                            
                            new_lead = Lead(
                                pk=pk,
                                username=username,
                                full_name=full_name,
                                bio=bio,
                                email=email,
                                is_private=is_private,
                                followers_count=followers,
                                source_account=target_username,
                                found_date=datetime.now().isoformat(),
                                last_scraped_date=datetime.now().isoformat(),
                                status="new",
                                change_details="",
                                avatar=f"https://api.dicebear.com/7.x/initials/svg?seed={username}",
                                external_url=details.get('external_url', '')
                            )
                            
                            db.session.add(new_lead)
                            db.session.commit() # Sofort speichern
                            
                            users_processed += 1
                            JOBS[target_username]['found'] = users_processed
                            JOBS[target_username]['message'] = f'{users_processed} neue Leads gefunden'
                            
                        except Exception as e:
                            print(f"Fehler bei User Detail {username}: {e}")
                            db.session.rollback()

                    # --- MODUS: SYNC ---
                    elif existing_lead and mode == "sync" and existing_lead.status != 'hidden':
                        updated = sync_single_lead_logic_db(cl, existing_lead)
                        if updated:
                             db.session.commit()
                             
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
        target_db = Target.query.filter_by(username=target_username).first()
        if not target_db:
            target_db = Target(username=target_username)
            db.session.add(target_db)
        
        target_db.last_scraped = datetime.now().isoformat()
        db.session.commit()
        
        JOBS[target_username]['status'] = 'finished'
        JOBS[target_username]['message'] = 'Fertig!'
        print(f"Fertig mit {target_username}")

def sync_single_lead_logic_db(client, lead_obj):
    """Prüft einen einzelnen Lead auf Updates (Datenbank Objekt)"""
    username = lead_obj.username
    try:
        details = client.user_by_username_v1(username)
        if not details: return False

        new_bio = details.get('biography', '')
        new_followers = details.get('follower_count', 0)
        new_email = details.get('public_email', '') or extract_email(new_bio)
        new_external_url = details.get('external_url', '')

        changes = []
        if new_bio != (lead_obj.bio or ''): changes.append("Bio neu")
        if new_external_url != (lead_obj.external_url or ''): changes.append("Link neu")
        
        old_followers = lead_obj.followers_count or 0
        if abs(new_followers - old_followers) > 10: 
            changes.append(f"Follower: {old_followers}->{new_followers}")

        new_status = lead_obj.status
        if lead_obj.status == 'not_found': new_status = 'active'
        if changes and new_status != 'blocked': new_status = 'changed'

        if changes:
             lead_obj.change_details = ", ".join(changes)
             lead_obj.last_updated_date = datetime.now().isoformat()

        # Objekt aktualisieren
        lead_obj.bio = new_bio
        lead_obj.email = new_email
        lead_obj.followers_count = new_followers
        lead_obj.last_scraped_date = datetime.now().isoformat()
        lead_obj.status = new_status
        lead_obj.external_url = new_external_url
        lead_obj.full_name = details.get('full_name', '')
        
        return True
    except Exception as e:
        print(f"Fehler Sync {username}: {e}")
        return False

# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get('password') == APP_PASSWORD:
        return jsonify({"success": True, "token": "session_valid"})
    return jsonify({"success": False}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    leads = Lead.query.all()
    targets = Target.query.all()
    
    data = {
        "leads": [l.to_dict() for l in leads],
        "targets": [t.to_dict() for t in targets]
    }
    return jsonify(data)

@app.route('/api/add-target', methods=['POST'])
def add_target():
    username = request.json.get('username')
    if not username: return jsonify({"error": "Missing username"}), 400
    
    # Target in DB eintragen wenn nicht existiert
    existing = Target.query.filter_by(username=username).first()
    if not existing:
        new_target = Target(username=username, last_scraped=None)
        db.session.add(new_target)
        db.session.commit()
    
    threading.Thread(target=scrape_target_logic, args=(username, "scan")).start()
    return jsonify({"message": f"Startet...", "job_id": username})

@app.route('/api/sync', methods=['POST'])
def sync_all():
    targets = Target.query.all()
    target_usernames = [t.username for t in targets]
    
    def run_sync():
        for t_user in target_usernames:
            scrape_target_logic(t_user, mode="sync")
            
    threading.Thread(target=run_sync).start()
    return jsonify({"message": "Full Sync gestartet..."})

@app.route('/api/sync-users', methods=['POST'])
def sync_users_endpoint():
    usernames = request.json.get('usernames', [])
    if not usernames: return jsonify({"error": "No usernames"}), 400
    
    job_id = f"sync_{int(time.time())}"
    JOBS[job_id] = {'status': 'running', 'found': 0, 'total': len(usernames), 'message': 'Starte Sync...'}

    def run_sync_job(job_id, users):
        with app.app_context():
            processed = 0
            cl = Client(token=API_KEY)
            
            for u in users:
                lead = Lead.query.filter_by(username=u).first()
                if lead:
                    updated = sync_single_lead_logic_db(cl, lead)
                    if updated:
                        db.session.commit()
                
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
        
        pk = int(user.get('pk'))
        
        existing = db.session.get(Lead, pk)
        if existing:
            print(f"User {username} existiert schon.")
            return

        bio = user.get('biography', '')
        email = user.get('public_email', '') or extract_email(bio)
        
        new_lead = Lead(
            pk=pk,
            username=user['username'],
            full_name=user['full_name'],
            bio=bio,
            email=email,
            is_private=bool(user.get('is_private')),
            followers_count=user.get('follower_count', 0),
            source_account='manually_added',
            found_date=datetime.now().isoformat(),
            last_scraped_date=datetime.now().isoformat(),
            status="new",
            change_details="",
            external_url=user.get('external_url', ''),
            avatar=f"https://api.dicebear.com/7.x/initials/svg?seed={user['username']}"
        )
        
        db.session.add(new_lead)
        db.session.commit()
        print(f"Manuell hinzugefuegt: {username}")
        
    except Exception as e:
        print(f"Fehler add_lead: {e}")
        db.session.rollback()

@app.route('/api/add-lead', methods=['POST'])
def add_lead():
    username = request.json.get('username')
    if not username: return jsonify({"error": "Missing username"}), 400
    try:
        # DB Logic muss im Main Thread oder mit AppContext laufen
        add_lead_logic(username)
        return jsonify({"message": f"OK", "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mark-exported', methods=['POST'])
def mark_exported():
    usernames = request.json.get('usernames', [])
    if not usernames: return jsonify({"error": "No usernames"}), 400
    
    now = datetime.now().isoformat()
    try:
        leads = Lead.query.filter(Lead.username.in_(usernames)).all()
        for lead in leads:
            lead.last_exported = now
        db.session.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    return jsonify({"success": True})

@app.route('/api/import', methods=['POST'])
def import_data():
    # Import ist komplexer mit DB, für jetzt vereinfacht:
    # Wir lesen das JSON und fügen fehlende Leads hinzu.
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        imported_data = json.load(file)
        new_leads_data = []
        if isinstance(imported_data, list):
            new_leads_data = imported_data
        elif isinstance(imported_data, dict) and "leads" in imported_data:
            new_leads_data = imported_data["leads"]
            
            # Targets importieren
            if "targets" in imported_data:
                for t in imported_data['targets']:
                    if not Target.query.filter_by(username=t['username']).first():
                        db.session.add(Target(username=t['username'], last_scraped=t.get('lastScraped')))
        
        added_count = 0
        updated_count = 0
        
        for l_data in new_leads_data:
            pk = int(l_data.get('pk'))
            if not pk: continue
            
            existing = db.session.get(Lead, pk)
            if existing:
                # Update Logic (simple overwrite for now)
                existing.email = l_data.get('email', existing.email)
                # ... weitere Felder bei Bedarf
                updated_count += 1
            else:
                new_lead = Lead(
                    pk=pk,
                    username=l_data.get('username'),
                    full_name=l_data.get('fullName'),
                    bio=l_data.get('bio'),
                    email=l_data.get('email'),
                    followers_count=l_data.get('followersCount', 0),
                    status=l_data.get('status', 'new'),
                    source_account=l_data.get('sourceAccount', 'import'),
                    found_date=l_data.get('foundDate', datetime.now().isoformat()),
                    last_scraped_date=l_data.get('lastScrapedDate', datetime.now().isoformat())
                )
                db.session.add(new_lead)
                added_count += 1
                
        db.session.commit()
        return jsonify({"success": True, "added": added_count, "updated": updated_count})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_data():
    # Erstellt JSON on-the-fly aus DB
    leads = Lead.query.all()
    targets = Target.query.all()
    data = {
        "leads": [l.to_dict() for l in leads],
        "targets": [t.to_dict() for t in targets]
    }
    
    # Temporäre Datei erstellen für Download
    temp_file = os.path.join(os.path.dirname(__file__), 'export_temp.json')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    return send_from_directory(os.path.dirname(__file__), 'export_temp.json', as_attachment=True)

@app.route('/api/delete-users', methods=['POST'])
def delete_users():
    pks = request.json.get('pks', [])
    if not pks: return jsonify({"error": "No IDs"}), 400
    
    try:
        # Lösche Leads deren PK in der Liste ist
        # Konvertiere pks zu Int sicherheitshalber
        pks_int = [int(p) for p in pks]
        stmt = Lead.__table__.delete().where(Lead.pk.in_(pks_int))
        result = db.session.execute(stmt)
        db.session.commit()
        
        return jsonify({"success": True, "deleted": result.rowcount})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/job-status/<username>', methods=['GET'])
def job_status(username):
    job = JOBS.get(username)
    if not job:
        return jsonify({'status': 'not_found'})
    return jsonify(job)

@app.route('/api/lead/update-status', methods=['POST'])
def update_status():
    data_in = request.json
    pk = int(data_in.get('pk'))
    status = data_in.get('status')
    
    lead = db.session.get(Lead, pk)
    if lead:
        lead.status = status
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

# Catch-All Route für React Router
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path.startswith('api/'):
        return jsonify({"error": "Not found"}), 404
    
    if path and path != 'index.html':
        try:
            return send_from_directory(app.static_folder, path)
        except:
            pass
    
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception as e:
        return f"Frontend not built yet. Error: {e}", 500

# --- INITIALISIERUNG ---

# Dies stellt sicher, dass Tabellen auch beim Deployment (Gunicorn) erstellt werden
with app.app_context():
    try:
        db.create_all()
        print("Datenbank Tabellen initialisiert (Deployment).")
    except Exception as e:
        print(f"DB Init Fehler: {e}")

if __name__ == '__main__':
    # Lokal starten auf Port 5000
    app.run(host='0.0.0.0', port=5000)
