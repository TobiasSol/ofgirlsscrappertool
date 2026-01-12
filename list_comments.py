import os
import json
import sys
from hikerapi import Client
from dotenv import load_dotenv

# Windows Encoding Fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
username = "chrissi.moves"

def list_all_comments():
    cl = Client(token=API_KEY)
    print(f"--- 🕵️ DETAILLIERTE KOMMENTAR-SUCHE FÜR: {username} ---")
    
    details = cl.user_by_username_v1(username)
    user_pk = details.get('pk')
    
    medias_data = cl.user_medias_chunk_v1(user_pk)
    if isinstance(medias_data, tuple): items = medias_data[0]
    else: items = medias_data
    if isinstance(items, list) and len(items) > 0 and isinstance(items[0], list):
        items = items[0]

    if not items:
        print("Keine Medien gefunden.")
        return

    print(f"Prüfe die ersten 5 Beiträge...\n")

    for i, m in enumerate(items[:5]):
        mid = m.get('pk') or m.get('id')
        code = m.get('code', 'Unknown')
        print(f"--- BEITRAG {i+1} (Code: {code}) ---")
        
        try:
            # Versuche Kommentare zu laden
            c_data = cl.media_comments(mid)
            if isinstance(c_data, tuple): c_data = c_data[0]
            
            if not c_data:
                print("Keine Kommentare gefunden.")
                continue
                
            found_any = False
            for c in c_data:
                author = c.get('user', {}).get('username', 'Unknown')
                text = c.get('text', '')
                
                # Wir geben alle Kommentare aus, markieren aber den Owner
                prefix = "🌟 [OWNER]" if author.lower() == username.lower() else "👤"
                print(f"{prefix} {author}: {text}")
                found_any = True
            
            if not found_any:
                print("Keine Kommentare in der Liste.")
                
        except Exception as e:
            print(f"Fehler beim Laden der Kommentare: {e}")
        print("\n")

if __name__ == "__main__":
    list_all_comments()
