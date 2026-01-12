import requests
import json
import time
import sys

# Encoding fix for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

base_url = "http://localhost:8000/api"
username = "fitchr1s"

def run_test():
    print(f"🚀 Starte realen Test auf localhost für: {username}")
    
    try:
        # 1. Analyse triggern
        res = requests.post(f"{base_url}/analyze-german", json={"usernames": [username]}, timeout=10)
        if res.status_code != 200:
            print(f"❌ API Fehler beim Starten: {res.status_code}")
            return
        
        job_id = res.json().get("job_id")
        print(f"✅ Job gestartet: {job_id}")
        
        # 2. Warten auf Abschluss
        max_attempts = 60 # 3 Minuten max
        attempt = 0
        while attempt < max_attempts:
            status_res = requests.get(f"{base_url}/get-job-status?username={job_id}", timeout=10)
            if status_res.status_code == 200:
                data = status_res.json()
                status = data.get("status")
                msg = data.get("message")
                print(f"⏳ [{attempt}] Status: {status} - {msg}")
                
                if status == "finished":
                    break
                if status == "error":
                    print(f"❌ Job-Fehler: {msg}")
                    return
            else:
                print(f"⚠️ Status-Check fehlgeschlagen.")
            
            time.sleep(3)
            attempt += 1
            
        # 3. Ergebnis abrufen
        print("\n--- ANALYSE ERGEBNIS VOM LOCALHOST ---")
        users_res = requests.get(f"{base_url}/users", timeout=10)
        leads = users_res.json().get("leads", [])
        for l in leads:
            if l["username"].lower() == username.lower():
                print(f"Nutzer: {l['username']}")
                print(f"DEUTSCH: {l['isGerman']}")
                print(f"ERGEBNIS: {l['germanCheckResult']}")
                
                # Wenn wir hier sind, haben wir das Ergebnis
                if l['isGerman']:
                    print("\n✅ BESTÄTIGT: Localhost erkennt den User als DEUTSCH.")
                else:
                    print("\n❌ NEGATIV: Localhost erkennt den User (noch) NICHT als DEUTSCH.")
                return

        print("❌ Nutzer nicht in der Datenbank gefunden.")

    except Exception as e:
        print(f"❌ Technischer Fehler: {e}")

if __name__ == "__main__":
    run_test()
