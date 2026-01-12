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
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLite Threading Fix
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
    
    # DACH-Analyse Felder
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

@app.after_request
def set_permissions_policy(response):
    response.headers['Permissions-Policy'] = 'local-network=()'
    return response

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal Server Error", "details": str(error)}), 500

JOBS = {}

# --- DACH ANALYSE LOGIK ---

DACH_LOCATIONS = [
    "germany", "deutschland", "berlin", "hamburg", "munich", "münchen", "köln", "wien", "zürich", "austria", "schweiz",
    "nrw", "bayern", "niedersachsen", "hessen", "baden-württemberg", "sachsen", "thüringen", "rlp", "pfalz",
    "bremen", "stuttgart", "düsseldorf", "leipzig", "dortmund", "essen", "frankfurt", "main", "mannheim", "kiel", "ostsee", "nordsee"
]
GERMAN_STOP_WORDS = [" der ", " die ", " das ", " ein ", " eine ", " ist ", " sind ", " nicht ", " und ", " mit ", " für ", " von ", " auf ", " aus ", " ich ", " mir ", " mein ", " auch ", " doch ", " mal ", " echt ", " schon ", " halt ", " hier ", " heute ", " alles ", "was ", " wer "]

def is_german_text(text):
    if not text: return False, ""
    t = text.lower()
    if any(c in t for c in ["ä", "ö", "ü", "ß"]): return True, "Umlaute"
    for loc in DACH_LOCATIONS:
        if re.search(r'(?:\s|#|[^a-z0-9])' + re.escape(loc) + r'(?:\s|,|!|\.|$)', t):
            return True, f"Ort: {loc.upper()}"
    if any(f in text for f in ["🇩🇪", "🇦🇹", "🇨🇭"]): return True, "Flagge"
    if any(w in t for w in ["impressum", "kontakt", "willkommen", "grüße", "liebe", "schokolade", "frauen", "verstehen", "mutter", "mama", "papa"]): return True, "D-Wort"
    if any(re.search(r'\b' + re.escape(w.strip()) + r'\b', t) for w in GERMAN_STOP_WORDS + ["is", "ne", "wa", "gell", "halt"]): return True, "D-Satzbau"
    return False, ""

def analyze_with_ai(text=None, image_url=None):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return None, "Kein Key"
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if image_url:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Antworte NUR mit 'JA: Grund' oder 'NEIN: Grund'. Ist auf diesem Bild/Video-Thumbnail DEUTSCHER Text eingeblendet (Untertitel oder Overlays)?"}, {"type": "image_url", "image_url": {"url": image_url}}]}],
                "max_tokens": 50
            }
        else:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Du bist ein Experte für DACH-Erkennung. Antworte immer 'JA: Grund' oder 'NEIN: Grund'. Analysiere Profil und Community-Kommentare."},
                    {"role": "user", "content": f"Ist dieser Instagram-User aus dem DACH-Raum? Kontext:\n{text}"}
                ],
                "max_tokens": 100
            }
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
        ans = res.json()['choices'][0]['message']['content'].strip()
        is_de = ans.upper().startswith("JA")
        reason = ans.split(":", 1)[1].strip() if ":" in ans else ans
        return is_de, reason
    except Exception as e: return None, str(e)

def analyze_german_deep(cl, username, update_fn=None):
    """Deep-Analyse mit Fokus auf Fan-Kommentare und Community."""
    try:
        if update_fn: update_fn("Lade Profil-Details...")
        details = cl.user_by_username_v1(username)
        if not details: return False, "Profil nicht geladen"
        
        user_pk = details.get('pk')
        bio = details.get('biography', '')
        full_name = details.get('full_name', '')
        
        # 1. Sofort-Check
        if update_fn: update_fn("Schnell-Check Bio/Name...")
        is_de, reason = is_german_text(f"{full_name} {bio}")
        if is_de: return True, f"Sofort: {reason}"
        
        # 2. Daten sammeln
        all_captions = []
        image_urls = []
        community_comments = [] 
        
        if update_fn: update_fn("Hole Medienliste...")
        medias_data = cl.user_medias_chunk_v1(user_pk)
        if medias_data:
            if isinstance(medias_data, tuple): items = medias_data[0]
            else: items = medias_data
            if isinstance(items, list) and len(items) > 0 and isinstance(items[0], list): items = items[0]
            
            if isinstance(items, list):
                total_media = len(items[:12])
                for idx, m in enumerate(items[:12]):
                    current_idx = idx + 1
                    if update_fn: update_fn(f"Verarbeite Beitrag {current_idx}/{total_media}...")
                    
                    if not isinstance(m, dict): continue
                    cap = m.get('caption_text') or ""
                    if cap: all_captions.append(cap)
                    img = m.get('thumbnail_url') or m.get('display_url')
                    if img: image_urls.append(img)
                    
                    # Fan-Kommentare (nur erste 4 Beiträge)
                    mid = m.get('pk') or m.get('id')
                    if mid and idx < 4 and len(community_comments) < 30:
                        try:
                            if update_fn: update_fn(f"Prüfe Fan-Kommentare in Beitrag {current_idx}/4...")
                            c_data = cl.media_comments(mid) if hasattr(cl, 'media_comments') else []
                            if isinstance(c_data, tuple): c_data = c_data[0]
                            if isinstance(c_data, list):
                                for c in c_data[:15]:
                                    comm_text = c.get('text', '')
                                    if comm_text: community_comments.append(comm_text)
                        except: pass

        # 3. KI TEXT-CHECK (Holistisch: Bio + Community)
        if update_fn: update_fn("KI analysiert Community & Profil...")
        context = f"BIO: {bio} | COMMUNITY_COMMS: {' | '.join(community_comments[:25])} | CAPS: {' | '.join(all_captions[:5])}"
        is_de_ai, ai_reason = analyze_with_ai(text=context)
        if is_de_ai: return True, f"Community: {ai_reason}"
        
        # 4. Vision Check
        if image_urls:
            for idx, img_url in enumerate(image_urls[:5]):
                if update_fn: update_fn(f"KI scannt Video-Overlay {idx+1}/5...")
                is_de_vis, vis_reason = analyze_with_ai(image_url=img_url)
                if is_de_vis: return True, f"Vision: {vis_reason}"
            
        return False, f"Nicht erkannt (KI: {ai_reason})"
    except Exception as e: return False, f"Crash: {str(e)}"

# --- SCRAPING LOGIK ---

def extract_email(text):
    if not text: return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""

def add_lead_logic(username):
    cl = Client(token=API_KEY)
    try:
        user = cl.user_by_username_v1(username)
        if not user: return False, "Nicht gefunden"
        pk = int(user.get('pk'))
        if db.session.get(Lead, pk): return True, "Bereits in DB"
        bio = user.get('biography', '')
        lead = Lead(pk=pk, username=user['username'], full_name=user['full_name'], bio=bio, 
                    email=user.get('public_email') or extract_email(bio), followers_count=user.get('follower_count', 0),
                    source_account='manually_added', found_date=datetime.now().isoformat(), status="new")
        db.session.add(lead)
        db.session.commit()
        return True, "Erfolg"
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def scrape_target_logic(target_username, mode="scan"):
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
                        bio = det.get('biography', '')
                        lead = Lead(pk=pk, username=u.get('username'), full_name=u.get('full_name'), bio=bio, 
                                    email=det.get('public_email') or extract_email(bio), followers_count=det.get('follower_count', 0),
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

# --- API ---

@app.route('/api/login', methods=['POST'])
def login():
    if request.json.get('password') == APP_PASSWORD: return jsonify({"success": True, "token": "ok"})
    return jsonify({"success": False}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify({"leads": [l.to_dict() for l in Lead.query.all()], "targets": [t.to_dict() for t in Target.query.all()]})

@app.route('/api/add-target', methods=['POST'])
def add_target():
    u = request.json.get('username')
    if not Target.query.filter_by(username=u).first():
        db.session.add(Target(username=u))
        db.session.commit()
    threading.Thread(target=scrape_target_logic, args=(u,)).start()
    return jsonify({"success": True, "job_id": u})

@app.route('/api/add-lead', methods=['POST'])
def add_lead():
    u = request.json.get('username')
    if not u: return jsonify({"error": "No username"}), 400
    ok, msg = add_lead_logic(u)
    return jsonify({"success": ok, "message": msg}), 200 if ok else 500

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
                def update_progress(msg):
                    JOBS[job_id]['message'] = f"[{idx+1}/{len(names)}] {name}: {msg}"
                
                update_progress("Wartet auf Analyse...")
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
    lead = db.session.get(Lead, int(data.get('pk')))
    if lead:
        lead.status = data.get('status')
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path.startswith('api/'): return jsonify({"error": "404"}), 404
    try: return send_from_directory(app.static_folder, path)
    except: return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        update_db_schema()
    app.run(host='0.0.0.0', port=8000)
