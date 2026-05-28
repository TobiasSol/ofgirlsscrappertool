"""Diagnose-Script: Prueft was die HikerAPI fuer ein nicht-existentes Profil zurueckgibt.
Hilft dabei die richtige Erkennung zu bauen.

Aufruf:  python test_profile_exists.py [username]
Default-Username: echt.mara (existiert laut User nicht mehr).
"""
import os
import sys
import json
import traceback

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from hikerapi import Client

API_KEY = os.environ.get("HIKERAPI_TOKEN")
if not API_KEY:
    sys.exit("HIKERAPI_TOKEN fehlt in .env")

username = sys.argv[1] if len(sys.argv) > 1 else "echt.mara"
print(f"=== HikerAPI Diagnose fuer Username: {username!r} ===\n")

cl = Client(token=API_KEY)


def safe_call(label, fn):
    print(f"--- {label} ---")
    try:
        result = fn()
        print(f"TYPE: {type(result).__name__}")
        if result is None:
            print("VALUE: None")
        elif isinstance(result, (dict, list)):
            try:
                print("VALUE:", json.dumps(result, indent=2, ensure_ascii=False, default=str)[:3000])
            except Exception:
                print("VALUE (repr):", repr(result)[:2000])
        else:
            print("VALUE (repr):", repr(result)[:2000])
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
    print()


# 1) Klassische v1 (was wir aktuell nutzen)
safe_call("user_by_username_v1", lambda: cl.user_by_username_v1(username))

# 2) v2-Variante - oft die genauere mit klarem 404 bei toten Profilen
if hasattr(cl, "user_by_username_v2"):
    safe_call("user_by_username_v2", lambda: cl.user_by_username_v2(username))
else:
    print("--- user_by_username_v2 ---")
    print("Methode existiert in hikerapi-Client nicht.\n")

# 3) GraphQL-Variante (manchmal frischer)
if hasattr(cl, "user_by_username_gql"):
    safe_call("user_by_username_gql", lambda: cl.user_by_username_gql(username))
else:
    print("--- user_by_username_gql ---")
    print("Methode existiert in hikerapi-Client nicht.\n")

# 4) Live-Web-Check direkt gegen Instagram (ohne HikerAPI), um zu sehen
#    ob das Profil "wirklich" weg ist - das ist die ground truth.
print("--- Direkter Instagram-Web-Check (ohne API) ---")
try:
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(f"https://www.instagram.com/{username}/", headers=headers, timeout=10, allow_redirects=False)
    print(f"HTTP-Status: {r.status_code}")
    print(f"Content-Length: {len(r.text)}")
    snippet = r.text[:1500].replace("\n", " ")
    print(f"Snippet: {snippet[:1000]}...")
    needles = [
        "Sorry, this page isn't available",
        "Diese Seite ist leider nicht verfuegbar",
        '"user_not_found"',
        "Page Not Found",
        "Page not found",
    ]
    found = [n for n in needles if n in r.text]
    if found:
        print(f"=> Profil existiert NICHT (Instagram-Hinweise gefunden: {found})")
    else:
        print("=> Profil scheint laut Instagram zu existieren (oder Login-Wall).")
except Exception as e:
    print(f"Web-Check fehlgeschlagen: {e}")

print("\n=== DONE ===")
