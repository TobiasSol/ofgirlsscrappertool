#!/bin/bash

# Backend starten (Hintergrund)
cd backend
pip install flask flask-cors hikerapi
python server.py &

# Zurück ins Root (wo jetzt das Frontend liegt)
cd ..

# Frontend starten
npm install
npm run dev
