"""Production-Entry fuer gunicorn (siehe .replit > [deployment]).
Wird auch von 'python main.py' im Dev-Modus genutzt.
"""
import sys
import os

# Pfad zum Backend hinzufuegen
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    print("Versuche Backend zu laden...")
    from backend.server import app, db, update_db_schema
    print("Backend erfolgreich geladen.")
except Exception as e:
    print(f"KRITISCHER FEHLER BEIM LADEN DES BACKENDS: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# WICHTIG: gunicorn ruft niemals __main__ auf, sondern importiert nur 'app'.
# Daher muss die DB-Initialisierung beim Modul-Import passieren, sonst
# fehlen auf einer frischen Cloud-DB alle Tabellen.
try:
    with app.app_context():
        print("Initialisiere Datenbank-Schema...")
        db.create_all()
        update_db_schema()
        print("✅ Datenbank bereit.")
except Exception as e:
    print(f"⚠️  WARNUNG: DB-Init beim Import fehlgeschlagen: {e}")

if __name__ == "__main__":
    try:
        print("Starte Flask Server auf Port 8000...")
        app.run(host='0.0.0.0', port=8000, debug=False)
    except Exception as e:
        print(f"FEHLER BEIM STARTEN DES SERVERS: {e}")
        import traceback
        traceback.print_exc()
