import json
import time
import random
import re
import threading
import os
import requests
import sys
from datetime import datetime, timedelta
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

# Env laden (sucht .env auch im Projekt-Root, falls Backend von woanders gestartet wird)
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- KONFIGURATION ---
API_KEY = os.environ.get("HIKERAPI_TOKEN")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

# Pflicht-Variablen pruefen, sonst frueh und klar abbrechen
_missing_env = [name for name, val in [("HIKERAPI_TOKEN", API_KEY), ("APP_PASSWORD", APP_PASSWORD)] if not val]
if _missing_env:
    print(f"❌ FEHLER: Pflicht-Umgebungsvariablen fehlen in .env: {', '.join(_missing_env)}")
    print("   Lege die Werte in der .env-Datei im Projekt-Root an (siehe .env.example).")
    sys.exit(1)

# Flask App Setup
app = Flask(__name__, static_folder='../dist', static_url_path='')
CORS(app)

# Erhöhe maximales Upload-Limit auf 50MB (für große Backups)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# --- DATENBANK KONFIGURATION ---
# Variante A: Lokal & Online nutzen IMMER dieselbe Cloud-DB.
#
# Vorrang-Reihenfolge (wichtig fuer Replit!):
#   1. NEON_DATABASE_URL  -> wenn gesetzt, wird IMMER diese genutzt.
#                            Damit kann Replit Agent uns die DB nicht "klauen",
#                            indem er DATABASE_URL auf seine interne Postgres
#                            umbiegt. Setze NEON_DATABASE_URL in den Replit-
#                            Secrets, dann ist DATABASE_URL egal.
#   2. DATABASE_URL       -> Fallback (lokal via .env, klassische Hoster).
DATABASE_URL = os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL")
DATABASE_URL_SOURCE = "NEON_DATABASE_URL" if os.environ.get("NEON_DATABASE_URL") else "DATABASE_URL"

if not DATABASE_URL:
    print("❌ FEHLER: Weder NEON_DATABASE_URL noch DATABASE_URL gesetzt.")
    print("   Trage deine Postgres-URL (z.B. von Neon) in die .env oder Replit-Secrets ein.")
    sys.exit(1)

# Heroku/Render/Neon liefern manchmal noch das alte 'postgres://'-Schema – SQLAlchemy braucht 'postgresql://'.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Warnung, falls aus Versehen eine Replit-interne DB benutzt wird.
_db_host = DATABASE_URL.split('@')[-1].split('/')[0].lower()
if any(marker in _db_host for marker in ("helium", "replit.dev", ".repl.co")):
    print(f"⚠️  WARNUNG: DATABASE_URL zeigt auf eine Replit-interne DB ({_db_host}).")
    print("   Setze NEON_DATABASE_URL in den Secrets, um deine externe Neon-DB zu erzwingen.")

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,    # tote Connections automatisch erkennen (wichtig fuer Neon-Sleep)
    "pool_recycle": 300,      # nach 5min Connection neu aufbauen
    "pool_size": 5,
    "max_overflow": 10,
}
print(f"--- ☁️  CLOUD-MODUS: verbunden mit {_db_host} (Quelle: {DATABASE_URL_SOURCE}) ---")

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

class ScanJob(db.Model):
    """Persistierter Scan-Status. Lebt in der DB damit:
       - Scans Reload, Worker-Restart und Render-Redeploy ueberleben
       - Der Status von jedem Geraet abrufbar ist
       - Mehrere gunicorn-Worker dieselbe Wahrheit sehen
    """
    __tablename__ = 'scan_jobs'
    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(20), nullable=False)        # 'dach' | 'target'
    label = db.Column(db.String(255), nullable=True)           # z.B. Target-Username oder "DACH-Scan (227 User)"
    status = db.Column(db.String(20), default='running')       # running | finished | error | stopped | interrupted
    total = db.Column(db.Integer, default=0)
    processed = db.Column(db.Integer, default=0)
    found = db.Column(db.Integer, default=0)                   # bei target-scan: wie viele neue Leads
    current_message = db.Column(db.Text, default='')
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_heartbeat = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    stop_requested = db.Column(db.Boolean, default=False)

    def to_dict(self):
        elapsed = None
        eta = None
        now = datetime.utcnow()
        if self.started_at:
            elapsed = int((now - self.started_at).total_seconds())
            if self.processed > 0 and self.total > 0 and self.status == 'running':
                rate = elapsed / self.processed                  # Sek pro User
                remaining = max(0, self.total - self.processed)
                eta = int(rate * remaining)
        return {
            "id": self.id,
            "type": self.job_type,
            "label": self.label,
            "status": self.status,
            "total": self.total,
            "processed": self.processed,
            "found": self.found,
            "percent": round((self.processed / self.total) * 100, 1) if self.total else 0,
            "message": self.current_message or "",
            "error": self.error_message,
            "stopRequested": self.stop_requested,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "lastHeartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "elapsedSeconds": elapsed,
            "etaSeconds": eta,
        }


def update_db_schema():
    """Idempotente Schema-Migrationen fuer bereits existierende DBs."""
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            # Lead-Tabelle: zwei Spalten nachruesten
            columns = [c['name'] for c in inspector.get_columns('leads')]
            if 'is_german' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE leads ADD COLUMN is_german BOOLEAN"))
                    conn.commit()
            if 'german_check_result' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE leads ADD COLUMN german_check_result TEXT"))
                    conn.commit()
        except Exception as e:
            print(f"⚠️  Schema-Migration (leads) uebersprungen: {e}")

        # Beim Start: alle "running" Jobs deren Heartbeat lange tot ist als 'interrupted' markieren.
        # Damit zeigt das Frontend nach einem Render-Redeploy nicht ewig einen toten Job.
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=2)
            stale = ScanJob.query.filter(
                ScanJob.status == 'running',
                ScanJob.last_heartbeat < cutoff,
            ).all()
            for j in stale:
                j.status = 'interrupted'
                j.error_message = 'Worker wurde neu gestartet (z.B. durch Deploy oder Crash).'
                j.finished_at = datetime.utcnow()
            if stale:
                db.session.commit()
                print(f"🧹 {len(stale)} verwaiste Scan-Jobs aufgeraeumt.")
        except Exception as e:
            print(f"⚠️  Cleanup verwaister Jobs uebersprungen: {e}")

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

JOBS = {}  # Legacy in-memory state - bleibt fuer Rueckwaertskompatibilitaet alter Endpunkte

# --- ScanJob Helpers ---

HEARTBEAT_INTERVAL_SECONDS = 5  # max. wie oft wir DB schreiben (vermeidet Spam)
_last_heartbeat_at = {}         # job_id -> datetime des letzten DB-Updates


def _job_should_stop(job_id):
    """Pruefe ob im DB-Job das stop_requested-Flag gesetzt ist.
    Wir muessen explizit refreshen, sonst sieht der Worker die Aenderung nicht.
    """
    try:
        job = db.session.get(ScanJob, job_id)
        if job is None:
            return True  # Job geloescht -> stoppen
        db.session.refresh(job)
        return bool(job.stop_requested)
    except Exception:
        db.session.rollback()
        return False


def _heartbeat(job_id, *, processed=None, found=None, message=None, force=False):
    """Schreibt Fortschritt + Heartbeat in die DB. Throttled auf
    HEARTBEAT_INTERVAL_SECONDS, ausser force=True.
    """
    now = datetime.utcnow()
    last = _last_heartbeat_at.get(job_id)
    if not force and last and (now - last).total_seconds() < HEARTBEAT_INTERVAL_SECONDS:
        # nur memory-update fuer message wenn wir eh nicht in DB schreiben
        return
    try:
        job = db.session.get(ScanJob, job_id)
        if job is None:
            return
        if processed is not None:
            job.processed = processed
        if found is not None:
            job.found = found
        if message is not None:
            job.current_message = message[:5000] if len(message) > 5000 else message
        job.last_heartbeat = now
        db.session.commit()
        _last_heartbeat_at[job_id] = now
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  heartbeat fehlgeschlagen fuer Job {job_id}: {e}")


def _finalize_job(job_id, status, error=None):
    """Markiert Job als finished/error/stopped und setzt finished_at."""
    try:
        job = db.session.get(ScanJob, job_id)
        if job is None:
            return
        job.status = status
        job.finished_at = datetime.utcnow()
        if error is not None:
            job.error_message = str(error)[:5000]
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  finalize fehlgeschlagen fuer Job {job_id}: {e}")
    finally:
        _last_heartbeat_at.pop(job_id, None)

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
    """Fragt OpenAI ob der User DACH ist. Liefert (is_de, kurz_tag).
    kurz_tag ist absichtlich auf 1-2 Woerter limitiert, damit das in der UI
    in eine Zeile passt (z.B. 'Hashtags', 'Bio', 'Ort', 'Slang').
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return None, "Kein Key"
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt_rules = (
            "Antworte AUSSCHLIESSLICH im Format 'JA:<tag>' oder 'NEIN:<tag>'. "
            "<tag> ist EIN Wort, max 15 Zeichen, kein Satz. "
            "Beispiele: JA:Bio, JA:Hashtag, JA:Ort, JA:Slang, NEIN:Englisch, NEIN:Spanisch."
        )
        if image_url:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": f"Ist auf diesem Bild deutscher Text/DACH-Bezug? {prompt_rules}"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]}],
                "max_tokens": 15,
            }
        else:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"Du erkennst DACH-User auf Instagram. {prompt_rules}"},
                    {"role": "user", "content": f"Kontext:\n{text}"},
                ],
                "max_tokens": 15,
            }
        res = requests.post("https://api.openai.com/v1/chat/completions",
                            headers=headers, json=payload, timeout=15)
        ans = res.json()['choices'][0]['message']['content'].strip()
        is_de = ans.upper().startswith("JA")
        tag = ans.split(":", 1)[1].strip() if ":" in ans else ans
        # Hard-Cap: nur erstes Wort, max 20 Zeichen
        tag = tag.split()[0] if tag.split() else tag
        tag = tag[:20].strip(".,;:!?-_")
        return is_de, tag or ("DE" if is_de else "kein DE")
    except Exception:
        return None, "Fehler"

def analyze_german_deep(cl, username, update_fn=None):
    try:
        if update_fn: update_fn("Lade Profil...")
        details = cl.user_by_username_v1(username)
        if not details: return False, "Profil nicht geladen"
        user_pk = details.get('pk')
        bio = details.get('biography', '')
        full_name = details.get('full_name', '')
        is_de, reason = is_german_text(f"{full_name} {bio}")
        if is_de: return True, f"✓ DE ({reason})"
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
        if is_de_ai: return True, f"✓ DE KI ({ai_reason})"
        if image_urls:
            for idx, img_url in enumerate(image_urls[:5]):
                is_de_vis, vis_reason = analyze_with_ai(image_url=img_url)
                if is_de_vis: return True, f"✓ DE Bild ({vis_reason})"
        return False, "✗ kein DE"
    except Exception as e: return False, f"Crash: {str(e)}"

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health():
    """Healthcheck fuer Replit/Cloud Run Deployment (siehe .replit)."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "db": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "degraded", "db": "error", "details": str(e)}), 503

@app.route('/api/login', methods=['POST'])
def login():
    """Prueft das Passwort serverseitig - Frontend hat keinen Klartext-Zugriff."""
    pw = (request.json or {}).get('password', '')
    if pw == APP_PASSWORD:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Falsches Passwort"}), 401

@app.route('/api/users', methods=['GET'])
def get_users():
    leads = Lead.query.all()
    targets = Target.query.all()
    return jsonify({"leads": [l.to_dict() for l in leads], "targets": [t.to_dict() for t in targets]})

@app.route('/api/add-target', methods=['POST'])
def add_target():
    u = request.json.get('username')
    if not u:
        return jsonify({"error": "Kein Username"}), 400
    if not Target.query.filter_by(username=u).first():
        db.session.add(Target(username=u))
        db.session.commit()

    existing = ScanJob.query.filter_by(status='running').first()
    if existing:
        return jsonify({"error": "Es laeuft bereits ein Scan", "activeJobId": existing.id}), 409

    job = ScanJob(
        job_type='target',
        label=f"Target: {u}",
        status='running',
        total=0,            # unbekannt - wird waehrend des Scans gesetzt
        processed=0,
        current_message='Lade...',
    )
    db.session.add(job)
    db.session.commit()
    job_id = job.id

    threading.Thread(target=scrape_target_logic, args=(u, job_id), daemon=True).start()
    return jsonify({"success": True, "job_id": job_id, "legacyKey": u})

@app.route('/api/get-job-status', methods=['GET'])
def get_job_status():
    """Legacy-Endpunkt. Sucht zuerst in der DB (wenn Frontend job_id schickt),
    sonst im alten in-memory JOBS-Dict.
    """
    raw = request.args.get('username')
    if raw and raw.isdigit():
        job = db.session.get(ScanJob, int(raw))
        if job:
            d = job.to_dict()
            d['found'] = job.found  # alter Frontend-Key
            return jsonify(d)
    job = JOBS.get(raw)
    if not job:
        return jsonify({"status": "not_found"})
    safe_job = {k: str(v) if k in ['message', 'status', 'start_time'] else v for k, v in job.items()}
    return jsonify(safe_job)


@app.route('/api/scans/active', methods=['GET'])
def scans_active():
    """Gibt den aktuell aktiven Scan zurueck (max. einer parallel).
    Wenn keiner laeuft: status='idle'.
    Frontend pollt das alle 2 Sek - das ist die Single-Source-of-Truth
    fuer den Header.
    """
    job = ScanJob.query.filter_by(status='running').order_by(ScanJob.started_at.desc()).first()
    if not job:
        # Optional: letzten beendeten Job zurueckgeben damit Frontend kurz "fertig" anzeigt
        recent = ScanJob.query.filter(
            ScanJob.status.in_(['finished', 'error', 'stopped', 'interrupted']),
            ScanJob.finished_at >= datetime.utcnow() - timedelta(seconds=10),
        ).order_by(ScanJob.finished_at.desc()).first()
        if recent:
            return jsonify({"active": False, "recent": recent.to_dict()})
        return jsonify({"active": False, "recent": None})
    return jsonify({"active": True, "job": job.to_dict()})


@app.route('/api/scans/<int:job_id>/stop', methods=['POST'])
def scans_stop(job_id):
    job = db.session.get(ScanJob, job_id)
    if not job:
        return jsonify({"error": "Job nicht gefunden"}), 404
    if job.status != 'running':
        return jsonify({"error": f"Job ist {job.status}, kann nicht gestoppt werden"}), 400
    job.stop_requested = True
    job.current_message = (job.current_message or "") + " | Stop angefordert..."
    db.session.commit()
    return jsonify({"success": True, "job": job.to_dict()})


@app.route('/api/scans/<int:job_id>', methods=['GET'])
def scans_get(job_id):
    job = db.session.get(ScanJob, job_id)
    if not job:
        return jsonify({"error": "Job nicht gefunden"}), 404
    return jsonify(job.to_dict())

@app.route('/api/analyze-german', methods=['POST'])
def analyze_german():
    names = request.json.get('usernames', [])
    if not names:
        return jsonify({"error": "Keine Usernamen uebergeben"}), 400

    # Verhindern, dass parallel mehrere DACH-Scans laufen.
    existing = ScanJob.query.filter_by(status='running').first()
    if existing:
        return jsonify({"error": "Es laeuft bereits ein Scan", "activeJobId": existing.id}), 409

    job = ScanJob(
        job_type='dach',
        label=f"DACH-Scan ({len(names)} User)",
        status='running',
        total=len(names),
        processed=0,
        current_message='Starte Scan...',
    )
    db.session.add(job)
    db.session.commit()
    job_id = job.id

    def run():
        with app.app_context():
            try:
                cl = Client(token=API_KEY)
                for idx, name in enumerate(names):
                    if _job_should_stop(job_id):
                        _finalize_job(job_id, 'stopped')
                        return

                    def update_progress(msg, _idx=idx, _name=name):
                        _heartbeat(job_id, message=f"[{_idx+1}/{len(names)}] {_name}: {msg}")

                    try:
                        lead = Lead.query.filter(Lead.username.ilike(name)).first()
                        if lead:
                            is_de, res = analyze_german_deep(cl, lead.username, update_fn=update_progress)
                            lead.is_german, lead.german_check_result = is_de, res
                            db.session.commit()
                    except Exception as inner:
                        db.session.rollback()
                        print(f"⚠️  Fehler bei {name}: {inner}")

                    _heartbeat(job_id, processed=idx + 1,
                               message=f"[{idx+1}/{len(names)}] {name}: fertig", force=True)

                _heartbeat(job_id, processed=len(names),
                           message='Scan abgeschlossen', force=True)
                _finalize_job(job_id, 'finished')
            except Exception as e:
                _finalize_job(job_id, 'error', error=e)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})

@app.route('/api/import', methods=['POST'])
def import_data():
    """Importiert ein Backup via Datei-Upload mit High-Performance Optimierung."""
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei gefunden"}), 400
    file = request.files['file']
    try:
        print("📥 IMPORT: Lese Datei...")
        data = json.load(file)
        leads = data.get('leads', [])
        targets = data.get('targets', [])
        
        # 1. Targets importieren (geringe Anzahl, daher einfach)
        for t in targets:
            if not Target.query.filter_by(username=t['username']).first():
                db.session.add(Target(username=t['username'], last_scraped=t.get('lastScraped')))
        
        # 2. Leads importieren (HIGH PERFORMANCE)
        # Hole alle existierenden PKs in einem Rutsch, um 37.000 einzelne Abfragen zu vermeiden
        print("📥 IMPORT: Prüfe existierende Datensätze...")
        existing_pks = {row[0] for row in db.session.query(Lead.pk).all()}
        
        added = 0
        batch_size = 1000
        
        print(f"📥 IMPORT: Verarbeite {len(leads)} potenzielle Leads...")
        for i, l in enumerate(leads):
            pk = l.get('pk')
            if pk and pk not in existing_pks:
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
                existing_pks.add(pk) # Verhindere Duplikate innerhalb der Datei
            
            # Zwischen-Commit alle 1000 Zeilen, um den Speicher zu schonen
            if added > 0 and added % batch_size == 0:
                db.session.flush()
        
        db.session.commit()
        print(f"✅ IMPORT ERFOLGREICH: {added} User hinzugefügt.")
        return jsonify({"success": True, "added": added})
    except Exception as e:
        db.session.rollback()
        print(f"❌ IMPORT FEHLER: {e}")
        import traceback
        traceback.print_exc()
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

def scrape_target_logic(target_username, job_id):
    """Folgt der Following-Liste eines Targets. Persistiert Fortschritt
    in der ScanJob-Tabelle, damit es Reload/Worker-Restart ueberlebt.
    """
    with app.app_context():
        try:
            cl = Client(token=API_KEY)
            t_info = cl.user_by_username_v1(target_username)
            t_id = t_info.get('pk')
            end_cursor = None
            processed = 0
            found = 0
            while True:
                if _job_should_stop(job_id):
                    _finalize_job(job_id, 'stopped')
                    return

                users, next_cursor = cl.user_following_chunk_gql(t_id, end_cursor=end_cursor)
                if not users:
                    break
                for u in users:
                    if _job_should_stop(job_id):
                        _finalize_job(job_id, 'stopped')
                        return
                    processed += 1
                    pk = int(u.get('pk') or u.get('id'))
                    if not db.session.get(Lead, pk):
                        try:
                            det = cl.user_by_username_v1(u.get('username'))
                            lead = Lead(
                                pk=pk, username=u.get('username'), full_name=u.get('full_name'),
                                bio=det.get('biography', ''), email=det.get('public_email'),
                                followers_count=det.get('follower_count', 0),
                                source_account=target_username,
                                found_date=datetime.now().isoformat(), status="new",
                            )
                            db.session.add(lead)
                            db.session.commit()
                            found += 1
                        except Exception as inner:
                            db.session.rollback()
                            print(f"⚠️  Konnte {u.get('username')} nicht laden: {inner}")
                    _heartbeat(job_id, processed=processed, found=found,
                               message=f"{processed} geprueft, {found} neu")
                if not next_cursor:
                    break
                end_cursor = next_cursor
                time.sleep(1)

            # Target last_scraped aktualisieren
            target_row = Target.query.filter_by(username=target_username).first()
            if target_row:
                target_row.last_scraped = datetime.now().isoformat()
                db.session.commit()

            _heartbeat(job_id, processed=processed, found=found,
                       message=f"Fertig: {found} neue Leads von {processed} geprueften", force=True)
            _finalize_job(job_id, 'finished')
        except Exception as e:
            _finalize_job(job_id, 'error', error=e)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        update_db_schema()
        seed_db_from_json()
    app.run(host='0.0.0.0', port=8000)
