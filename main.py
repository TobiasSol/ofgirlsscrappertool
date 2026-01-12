import sys
import os

# Pfad zum Backend hinzufügen
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

if __name__ == "__main__":
    try:
        with app.app_context():
            print("Initialisiere Datenbank...")
            db.create_all()
            update_db_schema()
            print("Datenbank bereit.")
        
        print("Starte Flask Server auf Port 8000...")
        app.run(host='0.0.0.0', port=8000, debug=False)
    except Exception as e:
        print(f"FEHLER BEIM STARTEN DES SERVERS: {e}")
        import traceback
        traceback.print_exc()
