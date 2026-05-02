# CrowdPulse
<<<<<<< HEAD

CrowdPulse is a full-stack crowd prediction prototype that blends real-time signals, future forecasting, location search, live check-ins, and a more human-centered interface for exploring crowded public places.

It was built to answer a practical question:

**"Before I go somewhere, how busy is it likely to be right now or later today?"**

## Why This Project Stands Out

- Real-time crowd visibility with WebSocket updates
- Future crowd forecasting by place, date, and hour
- User-driven place search instead of fixed demo locations
- Live check-ins that feed the crowd model
- Interactive maps, forecast charts, and crowd-level analytics
- Authenticated user flow with sign up, sign in, session restore, and logout
- A custom frontend presentation focused on warmth, clarity, and motion instead of plain dashboard styling

## What Recruiters Can See Here

This project demonstrates:

- Full-stack product thinking across UI, API design, and data flow
- Real-time system behavior using FastAPI plus WebSockets
- Frontend state handling in a non-trivial multi-view interface
- Integration of maps, charts, geocoding, and live event input
- A willingness to go beyond utility and make a technical project visually intentional

## Tech Stack

**Frontend**
- HTML
- CSS
- Vanilla JavaScript
- Leaflet
- Chart.js

**Backend**
- FastAPI
- Uvicorn
- Pydantic
- NumPy
- JWT authentication
- bcrypt

## Core Experience

After signing in, the user can:

1. Search for any place
2. View a real-time crowd estimate
3. See a 24-hour crowd curve
4. Predict crowd levels for a future date and time
5. Explore a live heatmap
6. Submit a live check-in to improve current signal quality

## Architecture Snapshot

```text
CrowdPulse-GitHub-Human-UI/
|-- backend/
|   |-- main.py
|   |-- requirements.txt
|   |-- .env.example
|   |-- ml/
|   |-- routers/
|   `-- utils/
|-- frontend/
|   |-- index.html
|   |-- css/
|   |   `-- style.css
|   `-- js/
|       `-- app.js
|-- .gitignore
`-- README.md
```

## API Surface

**Auth**
- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`

**Prediction**
- `POST /predict/`
- `GET /predict/place`
- `GET /predict/realtime`
- `GET /predict/heatmap`
- `GET /predict/all-places`

**Location**
- `POST /location/ping`
- `GET /location/heatmap-raw`

**Realtime**
- `WS /ws/live`

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/CrowdPulse-GitHub-Human-UI.git
cd CrowdPulse-GitHub-Human-UI
```

### 2. Start the backend

Windows PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload --port 8000
```

macOS / Linux:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### 3. Start the frontend

In a new terminal:

Windows PowerShell:

```powershell
cd frontend
python -m http.server 5500
```

macOS / Linux:

```bash
cd frontend
python3 -m http.server 5500
```

Open:

- `http://127.0.0.1:5500`
- FastAPI docs: `http://127.0.0.1:8000/docs`

## Environment Variables

Add your values to `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

## Product Notes

- The app currently uses in-memory auth storage, so user accounts reset when the backend restarts.
- The frontend uses public image URLs for the visual storytelling layer.
- This repository is positioned as a polished prototype with working real-time flows, not as a production-hardened deployment.

## Suggested GitHub Repo Description

Use this as the short GitHub description:

`Real-time crowd prediction web app with FastAPI, WebSockets, live check-ins, future forecasting, maps, and a custom human-centered UI.`

## Suggested Topics

Add these GitHub topics:

`fastapi` `websockets` `javascript` `leaflet` `chartjs` `crowd-prediction` `realtime-app` `full-stack-project` `ui-design`

## How To Push To GitHub

If this folder is not yet a git repository:

```bash
git init
git add .
git commit -m "Initial commit: CrowdPulse full-stack prototype"
git branch -M main
git remote add origin https://github.com/Bhargavi527/CrowdPulse
git push -u origin main
```

If the remote already exists:

```bash
git remote set-url origin https://github.com/YOUR_USERNAME/CrowdPulse-GitHub-Human-UI.git
git push -u origin main
```

## Next Improvements

- Persist users and live signals in a database
- Add tests for auth, prediction, and websocket flows
- Replace hardcoded secrets with environment-driven config
- Add deployment instructions for Render, Railway, or Vercel plus backend hosting
- Capture and include product screenshots or a short demo GIF in the README

## Author

Built by Bhargavi as a full-stack prototype focused on real-time prediction, usable UI, and recruiter-visible product polish.
=======
Full-stack crowd prediction app with real-time updates, future forecasting, interactive maps, and live check-ins.  CrowdPulse helps users check how busy places are now or later using real-time signals, forecasting, and an intuitive UI.  A full-stack  app for real-time crowd tracking, place search, forecasting, and heatmap-based insights.
>>>>>>> c7c45a460a590537a17f7bb71a7834b911356a7b
