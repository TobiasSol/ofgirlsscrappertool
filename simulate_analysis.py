import os
import json
import time
import sys
import requests
from hikerapi import Client
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

API_KEY = os.environ.get("HIKERAPI_TOKEN", "y0a9buus1f3z0vx3gqodr8lh11vvsxyh")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
username = "chrissi.moves"

def analyze_with_ai_local(text=None, image_url=None):
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    if image_url:
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": [{"type": "text", "text": "Antworte NUR JA oder NEIN. Ist auf dem Bild deutscher Text?"}, {"type": "image_url", "image_url": {"url": image_url}}]}], "max_tokens": 10}
    else:
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": "Antworte immer 'JA: Grund' oder 'NEIN: Grund'."}, {"role": "user", "content": f"Ist dieser User aus DACH? Kontext:\n{text}"}], "max_tokens": 100}
    res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
    return res.json()['choices'][0]['message']['content'].strip()

def run():
    cl = Client(token=API_KEY)
    print(f"--- START: {username} ---")
    details = cl.user_by_username_v1(username)
    bio = details.get('biography', '')
    print(f"BIO: {bio}")
    
    medias_data = cl.user_medias_chunk_v1(details.get('pk'))
    if isinstance(medias_data, tuple): items = medias_data[0]
    else: items = medias_data
    if items and isinstance(items[0], list): items = items[0]
    
    owner_comments = []
    image_urls = []
    
    for i, m in enumerate(items[:12]):
        img = m.get('thumbnail_url') or m.get('display_url')
        if img: image_urls.append(img)
        if i < 4:
            mid = m.get('pk') or m.get('id')
            try:
                c_data = cl.media_comments(mid)
                if isinstance(c_data, tuple): c_data = c_data[0]
                for c in c_data:
                    if c.get('user', {}).get('username', '').lower() == username.lower():
                        owner_comments.append(c.get('text', ''))
            except: pass

    print(f"KOMMENTARE GEFUNDEN: {len(owner_comments)}")
    context = f"BIO: {bio} | COMMS: {' | '.join(owner_comments[:5])}"
    res = analyze_with_ai_local(text=context)
    print(f"KI TEXT: {res}")
    
    if not res.upper().startswith("JA"):
        print("PRÜFE BILDER...")
        for i, url in enumerate(image_urls[:5]):
            v_res = analyze_with_ai_local(image_url=url)
            print(f"BILD {i+1}: {v_res}")
            if v_res.upper().startswith("JA"): break

if __name__ == "__main__":
    run()
