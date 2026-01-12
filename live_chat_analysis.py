import os
import json
import sys
import requests
from hikerapi import Client
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Lade .env explizit
load_dotenv()

# TOKEN direkt aus os.environ holen
API_KEY = os.getenv("HIKERAPI_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
username = "chrissi.moves"

def live_analysis():
    if not API_KEY:
        print("❌ HIKERAPI_TOKEN nicht gefunden!")
        return
    
    cl = Client(token=API_KEY)
    print(f"--- 🚀 LIVE-ANALYSE START: {username} ---")
    
    # 1. Profil
    print("STEP 1: Lade Profil-Details...")
    details = cl.user_by_username_v1(username)
    user_pk = details.get('pk')
    bio = details.get('biography', '')
    full_name = details.get('full_name', '')
    print(f"✅ Bio: {bio}")
    
    # 2. Medien & Kommentare
    print("\nSTEP 2: Lade Medien (12) und Kommentare (4 Posts)...")
    medias_data = cl.user_medias_chunk_v1(user_pk)
    
    if isinstance(medias_data, tuple): items = medias_data[0]
    else: items = medias_data
    if isinstance(items, list) and len(items) > 0 and isinstance(items[0], list): items = items[0]
    
    all_captions = []
    owner_comments = []
    image_urls = []
    
    if items:
        for i, m in enumerate(items[:12]):
            cap = m.get('caption_text') or ""
            if cap: all_captions.append(cap)
            img = m.get('thumbnail_url') or m.get('display_url')
            if img: image_urls.append(img)
            
            if i < 4:
                mid = m.get('pk') or m.get('id')
                try:
                    c_data = cl.media_comments(mid)
                    if isinstance(c_data, tuple): c_data = c_data[0]
                    if isinstance(c_data, list):
                        for c in c_data:
                            if c.get('user', {}).get('username', '').lower() == username.lower():
                                comm = c.get('text', '')
                                if comm: owner_comments.append(comm)
                except: pass

    # 3. Dossier
    print("\nSTEP 3: Dossier für KI erstellt.")
    context = f"BIO: {bio} | NAME: {full_name} | COMMS: {' | '.join(owner_comments)} | CAPS: {' | '.join(all_captions[:5])}"
    
    # 4. OpenAI
    print("\nSTEP 4: Sende Dossier an OpenAI...")
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Du bist ein Experte für DACH-Erkennung. Antworte immer 'JA: Grund' oder 'NEIN: Grund'."},
            {"role": "user", "content": f"Ist dieser Instagram-User aus Deutschland/Österreich/Schweiz? Kontext:\n{context}"}
        ],
        "max_tokens": 100
    }
    
    res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
    ans = res.json()['choices'][0]['message']['content'].strip()
    print(f"\n✨ KI TEXT-ERGEBNIS: {ans}")
    
    if not ans.upper().startswith("JA") and image_urls:
        print("\nSTEP 5: Starte Vision-Check...")
        for idx, url in enumerate(image_urls[:2]):
            v_payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Ist auf diesem Bild deutscher Text? Antworte JA: [Text] oder NEIN."}, {"type": "image_url", "image_url": {"url": url}}]}],
                "max_tokens": 50
            }
            v_res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=v_payload, timeout=15)
            v_ans = v_res.json()['choices'][0]['message']['content'].strip()
            print(f"   👁️ Bild {idx+1} Ergebnis: {v_ans}")
            if v_ans.upper().startswith("JA"): break

if __name__ == "__main__":
    live_analysis()
