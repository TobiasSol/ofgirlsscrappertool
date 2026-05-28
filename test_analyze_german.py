"""Direkter Test der analyze_german_deep-Funktion mit echt.mara.
Soll 'Profil existiert nicht' zurueckliefern statt 'kein DE'."""
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

# Backend importieren
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from server import analyze_german_deep, _profile_response_indicates_gone
from hikerapi import Client

API_KEY = os.environ.get("HIKERAPI_TOKEN")
cl = Client(token=API_KEY)

USERNAMES_TO_TEST = [
    ("echt.mara", False),    # Soll: existiert nicht
    ("instagram",  True),    # Soll: existiert (offizieller Account)
]

print("=== Test analyze_german_deep ===\n")
for name, expected_exists in USERNAMES_TO_TEST:
    print(f"--- {name} (erwartet: existiert={expected_exists}) ---")

    # Erst nochmal manuell den Raw-Response zeigen
    raw = cl.user_by_username_v1(name)
    print(f"  Raw-Response gone? -> {_profile_response_indicates_gone(raw)}")
    if isinstance(raw, dict):
        print(f"  exc_type='{raw.get('exc_type')}' pk='{raw.get('pk')}' username='{raw.get('username')}'")

    # Jetzt die volle Funktion (kann etwas dauern)
    is_de, reason, exists = analyze_german_deep(cl, name)
    status = "OK" if exists == expected_exists else "FAIL"
    print(f"  -> [{status}] is_de={is_de}, reason='{reason}', exists={exists}\n")

print("=== DONE ===")
