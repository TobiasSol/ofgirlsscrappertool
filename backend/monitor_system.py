import sqlite3
import json
import time
import random
import os
from datetime import datetime
from hikerapi import Client

# --- KONFIGURATION ---
API_KEY = "y0a9buus1f3z0vx3gqodr8lh11vvsxyh" 
# Nutzt die bestehende Datenbank im Root-Verzeichnis
DB_FILE = "../instagram_leads.db"

# WICHTIG: Speichert direkt in den Frontend-Ordner
EXPORT_FILE = "../frontend/src/data/users.json" 

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS targets (username TEXT PRIMARY KEY, last_scraped TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (pk INTEGER PRIMARY KEY, username TEXT, full_name TEXT, bio TEXT, email TEXT, is_private INTEGER, source_account TEXT, found_date TEXT, status TEXT)''')
    conn.commit()
    conn.close()
    print("✅ Datenbank initialisiert.")

def get_all_followings(client, user_id):
    users_collected = []
    end_cursor = None
    print(f"   ⏳ Lade Followings für ID {user_id}...")
    
    while True:
        try:
            users_list, next_cursor = client.user_following_chunk_gql(user_id, end_cursor=end_cursor)
            
            if users_list:
                users_collected.extend(users_list)
                print(f"   ... {len(users_collected)} geladen")
            
            if not next_cursor: break
            
            end_cursor = next_cursor
            time.sleep(random.uniform(1.5, 3.0))
            
        except Exception as e:
            print(f"   ⚠️ Fehler: {e}")
            break
            
    return users_collected

def get_user_details(client, username):
    try:
        return client.user_by_username_v1(username)
    except:
        return None

def run_daily_scan():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    cl = Client(token=API_KEY)

    c.execute("SELECT username FROM targets")
    targets = c.fetchall()

    if not targets:
        print("❌ Keine Ziel-Accounts definiert.")
        return

    for target_row in targets:
        target_username = target_row[0]
        print(f"\n🔎 Analysiere Ziel: {target_username}")

        try:
            target_info = cl.user_by_username_v1(target_username)
            target_id = target_info['pk']
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            continue

        current_followings = get_all_followings(cl, target_id)
        
        for user in current_followings:
            pk = user.get('pk') or user.get('id')
            username = user.get('username')
            
            c.execute("SELECT pk FROM leads WHERE pk=?", (pk,))
            if not c.fetchone():
                print(f"   ✨ NEU: {username}")
                details = get_user_details(cl, username)
                bio, email, is_private = "", "", 0
                if details:
                    bio = details.get('biography', '')
                    email = details.get('public_email', '')
                    is_private = 1 if details.get('is_private') else 0
                
                c.execute('''INSERT INTO leads (pk, username, full_name, bio, email, is_private, source_account, found_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (pk, username, user.get('full_name',''), bio, email, is_private, target_username, datetime.now().isoformat(), 'new'))
                conn.commit()
                time.sleep(1)

        c.execute("UPDATE targets SET last_scraped=? WHERE username=?", (datetime.now().isoformat(), target_username))
        conn.commit()
    
    conn.close()
    export_json()

def export_json():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY found_date DESC")
    rows = c.fetchall()
    
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
            "lastScraped": row['found_date'].split("T")[0],
            "sourceAccount": row['source_account'],
            "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={row['username']}"
        })
    
    os.makedirs(os.path.dirname(EXPORT_FILE), exist_ok=True)
    with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    print(f"\n📂 Exportiert nach: {EXPORT_FILE}")
    conn.close()

def main():
    init_db()
    while True:
        choice = input("\n1. Ziel adden\n2. Scan starten\n3. Export JSON\n4. Ziele zeigen\nq. Exit\nWahl: ").strip()
        if choice == '1':
            u = input("Username: ")
            conn = sqlite3.connect(DB_FILE)
            try: conn.execute("INSERT INTO targets (username) VALUES (?)", (u,)); conn.commit(); print("OK.")
            except: print("Existiert schon.")
            conn.close()
        elif choice == '2': run_daily_scan()
        elif choice == '3': export_json()
        elif choice == '4':
            conn = sqlite3.connect(DB_FILE)
            print(conn.execute("SELECT * FROM targets").fetchall())
            conn.close()
        elif choice == 'q': break

if __name__ == "__main__":
    main()

