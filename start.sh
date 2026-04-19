#!/bin/bash
# Replit-Workspace-Start (nicht fuer Production!).
# Production laeuft per .replit > [deployment] mit gunicorn.
#
# Voraussetzungen (einmalig in Replit-Secrets eintragen):
#   DATABASE_URL    - Neon-Connection-String
#   APP_PASSWORD    - Login-Passwort
#   HIKERAPI_TOKEN  - HikerAPI-Token
#   OPENAI_API_KEY  - (optional) fuer KI-DACH-Analyse

set -e

# Dependencies nur installieren wenn noetig
if [ ! -d "node_modules" ]; then
    echo "📦 Installiere Frontend-Dependencies..."
    npm install
fi

# Frontend + Backend parallel starten (siehe package.json > scripts.start)
npm run start
