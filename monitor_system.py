import sqlite3
import json
import time
import random
import os
from datetime import datetime
from hikerapi import Client

# --- KONFIGURATION ---
API_KEY = "y0a9buus1f3z0vx3gqodr8lh11vvsxyh" # Dein Key
DB_FILE = "instagram_leads.db"
EXPORT_FILE = "src/data/users.json" # Pfad zu deinem React Projekt Ordner anpassen!

# --- DATENBANK SETUP ---
def init_db():
    """Erstellt die Datenbank-Tabellen, falls sie nicht existieren."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Tabelle für die Ziel-Accounts (die wir überwachen)
    c.execute('''CREATE TABLE IF NOT EXISTS targets
                 (username TEXT PRIMARY KEY, last_scraped TEXT)''')

    # Tabelle für die gefundenen Leads (Followings)
    c.execute('''CREATE TABLE IF NOT EXISTS leads
                 (pk INTEGER PRIMARY KEY, 
                  username TEXT, 
                  full_name TEXT, 
                  bio TEXT, 
                  email TEXT, 
                  is_private INTEGER,
                  source_account TEXT,
                  found_date TEXT,
                  status TEXT)''') # status: 'new', 'contacted', 'ignored'
    
    conn.commit()
    conn.close()
    print("✅ Datenbank initialisiert.")

# --- HIKERAPI LOGIK ---
def get_all_followings(client, user_id):
    """Holt ALLE Followings eines Users via Pagination."""
    users_collected = []
    end_cursor = None
    
    print(f"   ⏳ Lade Followings für ID {user_id}...")
    
    while True:
        try:
            # Wir nutzen die stabile GQL Methode
            users_list, next_cursor = client.user_following_chunk_gql(user_id, end_cursor=end_cursor)
            
            if users_list:
                users_collected.extend(users_list)
                print(f"   ... {len(users_collected)} geladen (Chunk ok)")
            
            if not next_cursor:
                break
                
            end_cursor = next_cursor
            time.sleep(random.uniform(1.5, 3.0)) # Kurze Pause zum Schutz
            
        except Exception as e:
            print(f"   ⚠️ Fehler im Chunk: {e}")
            break
            
    return users_collected

def get_user_details(client, username_or_id):
    """Holt Details (Bio, Email) für einen EINZELNEN User."""
    try:
        # user_by_id_v1 ist oft günstiger/schneller wenn man die ID hat
        # Hier nutzen wir username_v1 für den Start
        user = client.user_by_username_v1(username_or_id)
        return user
    except:
        return None

# --- HAUPT-LOGIK: MONITORING ---
def run_daily_scan():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    cl = Client(token=API_KEY)

    # 1. Ziele laden
    c.execute("SELECT username FROM targets")
    targets = c.fetchall()

    if not targets:
        print("❌ Keine Ziel-Accounts definiert. Bitte erst hinzufügen!")
        return

    print(f"🚀 Starte Daily Scan für {len(targets)} Ziele...")

    for target_row in targets:
        target_username = target_row[0]
        print(f"\n🔎 Analysiere Ziel: {target_username}")

        # ID des Ziels holen
        try:
            target_info = cl.user_by_username_v1(target_username)
            target_id = target_info['pk']
        except Exception as e:
            print(f"   ❌ Konnte Ziel {target_username} nicht finden: {e}")
            continue

        # Aktuelle Followings live holen
        current_followings = get_all_followings(cl, target_id)
        
        new_leads_count = 0
        
        for user in current_followings:
            pk = user.get('pk') or user.get('id')
            username = user.get('username')
            full_name = user.get('full_name', '')
            
            # CHECK: Haben wir den schon in der DB?
            c.execute("SELECT pk FROM leads WHERE pk=?", (pk,))
            exists = c.fetchone()

            if not exists:
                # DAS IST EIN NEUER LEAD! 🎉
                print(f"   ✨ NEU GEFUNDEN: {username}")
                
                # Jetzt (und nur jetzt) holen wir teure Details wie Bio/Email
                # Um Credits zu sparen, machen wir das vielleicht nur bei keywords?
                # Fürs erste holen wir alles:
                details = get_user_details(cl, username)
                
                bio = ""
                email = ""
                is_private = 0
                
                if details:
                    bio = details.get('biography', '')
                    email = details.get('public_email', '')
                    is_private = 1 if details.get('is_private') else 0
                
                # Speichern
                c.execute('''INSERT INTO leads 
                             (pk, username, full_name, bio, email, is_private, source_account, found_date, status)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (pk, username, full_name, bio, email, is_private, target_username, datetime.now().isoformat(), 'new'))
                conn.commit()
                new_leads_count += 1
                
                time.sleep(1) # Schutzpause bei Detail-Abfrage

        # Update "Last Scraped" für das Ziel
        c.execute("UPDATE targets SET last_scraped=? WHERE username=?", (datetime.now().isoformat(), target_username))
        conn.commit()
        print(f"✅ Analyse für {target_username} fertig. {new_leads_count} neue Leads gespeichert.")

    conn.close()
    export_json()

# --- EXPORT FÜR DAS DASHBOARD ---
def export_json():
    """Exportiert die DB als JSON, damit dein React Dashboard sie lesen kann."""
    conn = sqlite3.connect(DB_FILE)
    # Row Factory für Dictionary-Zugriff
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM leads ORDER BY found_date DESC")
    rows = c.fetchall()
    
    # Umwandeln in das Format, das dein React App.jsx erwartet
    export_data = []
    for row in rows:
        export_data.append({
            "id": f"user_{row['pk']}",
            "pk": row['pk'],
            "username": row['username'],
            "fullName": row['full_name'],
            "bio": row['bio'],
            "email": row['email'],
            "isPrivate": bool(row['is_private']),
            "status": row['status'],
            "lastScraped": row['found_date'].split("T")[0], # Nur Datum
            "sourceAccount": row['source_account'],
            "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={row['username']}" # Platzhalter Avatar
        })
    
    # Sicherstellen, dass das Verzeichnis existiert
    os.makedirs(os.path.dirname(EXPORT_FILE), exist_ok=True)
    
    with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n📂 Daten exportiert nach: {EXPORT_FILE}")
    conn.close()

# --- MENÜ ---
def main():
    init_db()
    while True:
        print("\n--- INSTAGRAM MONITOR SYSTEM ---")
        print("1. Ziel-Account hinzufügen (Source)")
        print("2. Manuellen Scan starten (Alle Ziele)")
        print("3. JSON neu exportieren")
        print("4. Alle Ziele anzeigen")
        print("q. Beenden")
        
        choice = input("Wahl: ").strip().lower()
        
        if choice == '1':
            u = input("Welchen Account überwachen? (z.B. bestfansoriginal): ")
            conn = sqlite3.connect(DB_FILE)
            try:
                conn.execute("INSERT INTO targets (username) VALUES (?)", (u,))
                conn.commit()
                print("Gespeichert.")
            except sqlite3.IntegrityError:
                print("Dieser Account wird bereits überwacht.")
            conn.close()
            
        elif choice == '2':
            run_daily_scan()
            
        elif choice == '3':
            export_json()

        elif choice == '4':
            conn = sqlite3.connect(DB_FILE)
            rows = conn.execute("SELECT * FROM targets").fetchall()
            for r in rows:
                print(f"- {r[0]} (Letzter Scan: {r[1]})")
            conn.close()
            
        elif choice == 'q':
            break

if __name__ == "__main__":
    main()