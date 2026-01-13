import json
import time
import random
import re
import threading
import os
import requests
import sys
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

# Encoding Fix für Windows Terminals (Emojis)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except: pass

from flask_cors import CORS
from hikerapi import Client
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from dotenv import load_dotenv

# Optional: Langdetect
try:
    from langdetect import detect
except ImportError:
    detect = None

# Env laden
load_dotenv()

# --- KONFIGURATION ---
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "Tobideno85!")

# Flask App Setup
app = Flask(__name__, static_folder='../dist', static_url_path='')
CORS(app)

# --- DATENBANK KONFIGURATION ---
if sys.platform == "win32":
    db_path = os.path.join(os.getcwd(), 'lokal.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    print(f"--- 🖥️ LOKAL-MODUS: Nutze {db_path} ---")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {"check_same_thread": False}
    }
else:
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
        return {"username": self.username, "lastScraped": self.last_scraped}

class Lead(db.Model):
    __tablename__ = 'leads'
    pk = db.Column(db.BigInteger, primary_key=True)
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
    is_german = db.Column(db.Boolean, default=None, nullable=True)
    german_check_result = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "pk": self.pk, "id": f"user_{self.pk}", "username": self.username,
            "fullName": self.full_name, "bio": self.bio, "email": self.email,
            "isPrivate": self.is_private, "followersCount": self.followers_count,
            "sourceAccount": self.source_account, "foundDate": self.found_date,
            "lastScrapedDate": self.last_scraped_date, "status": self.status,
            "changeDetails": self.change_details, "avatar": self.avatar,
            "externalUrl": self.external_url, "lastUpdatedDate": self.last_updated_date,
            "lastExported": self.last_exported, "isGerman": self.is_german,
            "germanCheckResult": self.german_check_result
        }

def update_db_schema():
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('leads')]
            if 'is_german' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE leads ADD COLUMN is_german BOOLEAN"))
                    conn.commit()
            if 'german_check_result' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE leads ADD COLUMN german_check_result TEXT"))
                    conn.commit()
        except: pass

def seed_db_from_json():
    try:
        json_path = os.path.join(os.getcwd(), 'export_temp.json')
        if not os.path.exists(json_path): return
        with app.app_context():
            if Lead.query.first() is not None: return
            print("--- 📥 AUTO-IMPORT: Starte Import... ---")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for t in data.get('targets', []):
                if not Target.query.filter_by(username=t['username']).first():
                    db.session.add(Target(username=t['username'], last_scraped=t.get('lastScraped')))
            leads_list = data.get('leads', [])
            for l in leads_list:
                pk = l.get('pk')
                if pk and not db.session.get(Lead, pk):
                    new_lead = Lead(
                        pk=pk, username=l.get('username'), full_name=l.get('fullName'),
                        bio=l.get('bio'), email=l.get('email'), is_private=l.get('isPrivate', False),
                        followers_count=l.get('followersCount', 0), source_account=l.get('sourceAccount'),
                        found_date=l.get('foundDate'), last_scraped_date=l.get('lastScrapedDate'),
                        status=l.get('status', 'new'), change_details=l.get('changeDetails', ''),
                        avatar=l.get('avatar'), external_url=l.get('externalUrl'),
                        last_updated_date=l.get('lastUpdatedDate'), last_exported=l.get('lastExported'),
                        is_german=l.get('isGerman'), german_check_result=l.get('germanCheckResult')
                    )
                    db.session.add(new_lead)
            db.session.commit()
            print(f"✅ ERFOLG: {len(leads_list)} User wurden importiert.")
    except Exception as e: print(f"❌ AUTO-IMPORT FEHLER: {e}")

@app.after_request
def set_permissions_policy(response):
    response.headers['Permissions-Policy'] = 'local-network=()'
    return response

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal Server Error", "details": str(error)}), 500

JOBS = {}

# --- DACH ANALYSE LOGIK ---

DACH_LOCATIONS = ["germany", "deutschland", "berlin", "hamburg", "munich", "münchen", "köln", "wien", "zürich", "austria", "schweiz", "nrw", "bayern"]
GERMAN_STOP_WORDS = [" der ", " die ", " das ", " ist ", " sind ", " nicht ", " und ", " ich ", " auch ", " mal ", " echt ", " schon ", " halt "]

def is_german_text(text):
    if not text: return False, ""
    t = text.lower()
    if any(c in t for c in ["ä", "ö", "ü", "ß"]): return True, "Umlaute"
    for loc in DACH_LOCATIONS:
        if re.search(r'(?:\s|#|[^a-z0-9])' + re.escape(loc) + r'(?:\s|,|!|\.|$)', t): return True, f"Ort: {loc.upper()}"
    if any(f in text for f in ["🇩🇪", "🇦🇹", "🇨🇭"]): return True, "Flagge"
    if any(w in t for w in ["impressum", "kontakt", "willkommen"]): return True, "Keyword"
    return False, ""

def analyze_with_ai(text=None, image_url=None):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return None, "Kein Key"
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if image_url:
            payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": [{"type": "text", "text": "Antworte NUR mit 'JA: Grund' oder 'NEIN: Grund'. Ist auf diesem Bild DEUTSCHER Text?"}, {"type": "image_url", "image_url": {"url": image_url}}]}], "max_tokens": 50}
        else:
            payload = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": "Experte für DACH-Erkennung. Antworte 'JA: Grund' oder 'NEIN: Grund'."}, {"role": "user", "content": f"Ist dieser Instagram-User aus DACH? Kontext:\n{text}"}], "max_tokens": 100}
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
        ans = res.json()['choices'][0]['message']['content'].strip()
        is_de = ans.upper().startswith("JA")
        reason = ans.split(":", 1)[1].strip() if ":" in ans else ans
        return is_de, reason
    except: return None, "Fehler"

def analyze_german_deep(cl, username, update_fn=None):
    try:
        if update_fn: update_fn("Lade Profil...")
        details = cl.user_by_username_v1(username)
        if not details: return False, "Profil nicht geladen"
        user_pk = details.get('pk')
        bio = details.get('biography', '')
        full_name = details.get('full_name', '')
        is_de, reason = is_german_text(f"{full_name} {bio}")
        if is_de: return True, f"Sofort: {reason}"
        all_captions = []
        image_urls = []
        community_comments = []
        medias_data = cl.user_medias_chunk_v1(user_pk)
        if medias_data:
            if isinstance(medias_data, tuple): items = medias_data[0]
            else: items = medias_data
            if isinstance(items, list) and len(items) > 0 and isinstance(items[0], list): items = items[0]
            if isinstance(items, list):
                for idx, m in enumerate(items[:12]):
                    if not isinstance(m, dict): continue
                    cap = m.get('caption_text') or ""
                    if cap: all_captions.append(cap)
                    img = m.get('thumbnail_url') or m.get('display_url')
                    if img: image_urls.append(img)
                    mid = m.get('pk') or m.get('id')
                    if mid and idx < 4 and len(community_comments) < 20:
                        try:
                            c_data = cl.media_comments(mid) if hasattr(cl, 'media_comments') else []
                            if isinstance(c_data, tuple): c_data = c_data[0]
                            if isinstance(c_data, list):
                                for c in c_data[:15]:
                                    comm = c.get('text', '')
                                    if comm: community_comments.append(comm)
                        except: pass
        context = f"BIO: {bio} | NAME: {full_name} | COMMS: {' | '.join(community_comments[:15])} | CAPS: {' | '.join(all_captions[:5])}"
        is_de_ai, ai_reason = analyze_with_ai(text=context)
        if is_de_ai: return True, f"KI (Text): {ai_reason}"
        if image_urls:
            for idx, img_url in enumerate(image_urls[:5]):
                is_de_vis, vis_reason = analyze_with_ai(image_url=img_url)
                if is_de_vis: return True, f"Vision: {vis_reason}"
        return False, f"Nicht erkannt (KI: {ai_reason})"
    except Exception as e: return False, f"Crash: {str(e)}"

@app.route('/api/users', methods=['GET'])
def get_users():
    leads = Lead.query.all()
    targets = Target.query.all()
    return jsonify({"leads": [l.to_dict() for l in leads], "targets": [t.to_dict() for t in targets]})

@app.route('/api/add-target', methods=['POST'])
def add_target():
    u = request.json.get('username')
    if not Target.query.filter_by(username=u).first():
        db.session.add(Target(username=u))
        db.session.commit()
    threading.Thread(target=scrape_target_logic, args=(u,)).start()
    return jsonify({"success": True, "job_id": u})

@app.route('/api/get-job-status', methods=['GET'])
def get_job_status():
    u = request.args.get('username')
    job = JOBS.get(u)
    if not job: return jsonify({"status": "not_found"})
    safe_job = {k: str(v) if k in ['message', 'status', 'start_time'] else v for k,v in job.items()}
    return jsonify(safe_job)

@app.route('/api/analyze-german', methods=['POST'])
def analyze_german():
    names = request.json.get('usernames', [])
    job_id = f"dach_{int(time.time())}"
    JOBS[job_id] = {'status': 'running', 'found': 0, 'total': len(names), 'message': 'Starte Scan...'}
    def run():
        with app.app_context():
            cl = Client(token=API_KEY)
            for idx, name in enumerate(names):
                def update_progress(msg): JOBS[job_id]['message'] = f"[{idx+1}/{len(names)}] {name}: {msg}"
                lead = Lead.query.filter(Lead.username.ilike(name)).first()
                if lead:
                    is_de, res = analyze_german_deep(cl, lead.username, update_fn=update_progress)
                    lead.is_german, lead.german_check_result = is_de, res
                    db.session.commit()
                JOBS[job_id]['found'] = idx + 1
            JOBS[job_id]['status'] = 'finished'
            JOBS[job_id]['message'] = 'Scan abgeschlossen'
    threading.Thread(target=run).start()
    return jsonify({"success": True, "job_id": job_id})

@app.route('/api/import', methods=['POST'])
def import_data():
    """Importiert ein Backup via Datei-Upload."""
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei gefunden"}), 400
    file = request.files['file']
    try:
        data = json.load(file)
        leads = data.get('leads', [])
        targets = data.get('targets', [])
        
        # 1. Targets
        for t in targets:
            if not Target.query.filter_by(username=t['username']).first():
                db.session.add(Target(username=t['username'], last_scraped=t.get('lastScraped')))
        
        # 2. Leads
        added = 0
        for l in leads:
            pk = l.get('pk')
            if pk and not db.session.get(Lead, pk):
                new_lead = Lead(
                    pk=pk, username=l.get('username'), full_name=l.get('fullName'),
                    bio=l.get('bio'), email=l.get('email'), is_private=l.get('isPrivate', False),
                    followers_count=l.get('followersCount', 0), source_account=l.get('sourceAccount'),
                    found_date=l.get('foundDate'), last_scraped_date=l.get('lastScrapedDate'),
                    status=l.get('status', 'new'), change_details=l.get('changeDetails', ''),
                    avatar=l.get('avatar'), external_url=l.get('externalUrl'),
                    last_updated_date=l.get('lastUpdatedDate'), last_exported=l.get('lastExported'),
                    is_german=l.get('isGerman'), german_check_result=l.get('germanCheckResult')
                )
                db.session.add(new_lead)
                added += 1
        
        db.session.commit()
        return jsonify({"success": True, "added": added})
    except Exception as e:
        db.session.rollback()
        print(f"❌ IMPORT FEHLER: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_data():
    """Erstellt ein Backup als JSON-Download."""
    try:
        leads = Lead.query.all()
        targets = Target.query.all()
        data = {
            "leads": [l.to_dict() for l in leads],
            "targets": [t.to_dict() for t in targets]
        }
        response = jsonify(data)
        response.headers.set('Content-Disposition', 'attachment', filename='insta_backup.json')
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-users', methods=['POST'])
def delete_users():
    pks = request.json.get('pks', [])
    try:
        pks_int = [int(p) for p in pks]
        Lead.query.filter(Lead.pk.in_(pks_int)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/lead/update-status', methods=['POST'])
def update_status():
    data = request.json
    try:
        pk_val = int(data.get('pk'))
        status_val = data.get('status')
        print(f"DEBUG: Update Status für {pk_val} auf {status_val}")
        lead = db.session.get(Lead, pk_val)
        if lead:
            lead.status = status_val
            db.session.commit()
            print(f"✅ Status erfolgreich gespeichert.")
            return jsonify({"success": True})
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/add-lead', methods=['POST'])
def add_lead():
    u = request.json.get('username')
    if not u: return jsonify({"error": "No username"}), 400
    try:
        cl = Client(token=API_KEY)
        user = cl.user_by_username_v1(u)
        if not user: return jsonify({"error": "Nicht gefunden"}), 404
        pk = int(user.get('pk'))
        if not db.session.get(Lead, pk):
            new_lead = Lead(pk=pk, username=user['username'], full_name=user['full_name'], bio=user.get('biography', ''),
                            email=user.get('public_email'), followers_count=user.get('follower_count', 0),
                            source_account='manually_added', found_date=datetime.now().isoformat(), status="new")
            db.session.add(new_lead)
            db.session.commit()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path.startswith('api/'): return jsonify({"error": "404"}), 404
    try: return send_from_directory(app.static_folder, path)
    except: return send_from_directory(app.static_folder, 'index.html')

def scrape_target_logic(target_username):
    global JOBS
    JOBS[target_username] = {'status': 'running', 'found': 0, 'message': 'Lade...', 'start_time': datetime.now().isoformat()}
    with app.app_context():
        cl = Client(token=API_KEY)
        try:
            t_info = cl.user_by_username_v1(target_username)
            t_id = t_info.get('pk')
            end_cursor = None
            found = 0
            while True:
                users, next_cursor = cl.user_following_chunk_gql(t_id, end_cursor=end_cursor)
                if not users: break
                for u in users:
                    pk = int(u.get('pk') or u.get('id'))
                    if not db.session.get(Lead, pk):
                        det = cl.user_by_username_v1(u.get('username'))
                        lead = Lead(pk=pk, username=u.get('username'), full_name=u.get('full_name'), bio=det.get('biography', ''), 
                                    email=det.get('public_email'), followers_count=det.get('follower_count', 0),
                                    source_account=target_username, found_date=datetime.now().isoformat(), status="new")
                        db.session.add(lead)
                        db.session.commit()
                        found += 1
                        JOBS[target_username]['found'] = found
                        JOBS[target_username]['message'] = f"{found} gefunden"
                if not next_cursor: break
                end_cursor = next_cursor
                time.sleep(1)
            JOBS[target_username]['status'] = 'finished'
        except Exception as e:
            JOBS[target_username]['status'] = 'error'
            JOBS[target_username]['message'] = str(e)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        update_db_schema()
        seed_db_from_json()
    app.run(host='0.0.0.0', port=8000)
