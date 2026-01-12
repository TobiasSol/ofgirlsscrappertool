import os
import json
import sys
from hikerapi import Client
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
username = "chrissi.moves"

def extreme_debug():
    cl = Client(token=API_KEY)
    print(f"--- 🕵️ EXTREME DEBUG FÜR: {username} ---")
    
    details = cl.user_by_username_v1(username)
    user_pk = details.get('pk')
    print(f"User PK: {user_pk}")
    
    print("Lade Medien...")
    medias = cl.user_medias_chunk_v1(user_pk)
    
    print(f"Typ von medias: {type(medias)}")
    if isinstance(medias, tuple):
        print(f"Medias ist ein Tuple mit Länge {len(medias)}")
        medias = medias[0]
    
    if isinstance(medias, list):
        print(f"Anzahl Items in Liste: {len(medias)}")
        if len(medias) > 0:
            first = medias[0]
            print(f"Typ des ersten Items: {type(first)}")
            
            # Falls Liste in Liste
            if isinstance(first, list):
                print("⚠️ LISTE IN LISTE ERKANNT! Packe aus...")
                medias = first
                first = medias[0]
            
            if isinstance(first, dict):
                print(f"Keys im ersten Media-Objekt: {list(first.keys())}")
                cap = first.get('caption')
                print(f"Caption gefunden? {'JA' if cap else 'NEIN'}")
                if cap:
                    print(f"Caption Inhalt: {cap.get('text') if isinstance(cap, dict) else cap}")
                
                # Kommentar Test
                mid = first.get('pk') or first.get('id')
                print(f"Media ID für Kommentare: {mid}")
                try:
                    comms = cl.media_comments_v1(mid)
                    print(f"Kommentare geladen: {type(comms)}")
                except Exception as e:
                    print(f"Kommentar-Fehler: {e}")
    else:
        print("❌ FEHLER: Medias ist keine Liste!")

if __name__ == "__main__":
    extreme_debug()
