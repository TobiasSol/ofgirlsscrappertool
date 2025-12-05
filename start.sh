#!/bin/bash

# Backend starten (Hintergrund)
cd backend
pip install flask flask-cors hikerapi
python server.py &

# Frontend starten
cd ../frontend
npm install
npm run dev

