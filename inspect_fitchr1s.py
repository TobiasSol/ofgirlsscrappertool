import os
import json
from hikerapi import Client
from dotenv import load_dotenv
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
username = "fitchr1s"

def inspect_data():
    cl = Client(token=API_KEY)
    details = cl.user_by_username_v1(username)
    user_pk = details.get('pk')
    
    owner_comments = []
    captions = []
    
    medias_data = cl.user_medias_chunk_v1(user_pk)
    if isinstance(medias_data, tuple): items = medias_data[0]
    else: items = medias_data
    if isinstance(items, list) and len(items) > 0 and isinstance(items[0], list):
        items = items[0]

    if items:
        for m in items[:5]:
            if not isinstance(m, dict): continue
            cap = m.get('caption_text') or ""
            if cap: captions.append(cap)
            
            mid = m.get('pk') or m.get('id')
            try:
                c_data = cl.media_comments(mid)
                if isinstance(c_data, tuple): c_data = c_data[0]
                if c_data:
                    for c in c_data:
                        if c.get('user', {}).get('username', '').lower() == username.lower():
                            owner_comments.append(c.get('text', ''))
            except: pass

    print("\n--- ECHTE DATEN VON FITCHR1S ---")
    print(f"BIO: {details.get('biography')}")
    print(f"EIGENE KOMMENTARE: {owner_comments}")
    print(f"CAPTIONS: {captions[:3]}")

if __name__ == "__main__":
    inspect_data()
