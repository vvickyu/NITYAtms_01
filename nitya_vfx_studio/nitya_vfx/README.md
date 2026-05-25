# 🎬 Nitya VFX Studio — Production Portal

Flask + SQLite backend. All data saves permanently to `nitya_vfx.db`.

---

## ▶️ HOW TO RUN (Windows)

### Step 1 — Install Python
Download from https://python.org (check "Add to PATH" during install)

### Step 2 — Install dependencies
Open Command Prompt (cmd) in this folder and run:
```
pip install flask flask-cors
```

### Step 3 — Start the server
```
python app.py
```

### Step 4 — Open the app
Open your browser and go to:
```
http://localhost:5000
```

---

## 🌐 TO SHARE ON YOUR NETWORK (all artists on same WiFi)

Find your computer's IP address:
- Open cmd → type `ipconfig` → look for "IPv4 Address" e.g. `192.168.1.10`

Artists open: `http://192.168.1.10:5000`

---

## 🌍 TO PUT ONLINE (Internet access from anywhere)

### Option A — PythonAnywhere (Free, easy)
1. Go to https://www.pythonanywhere.com → Sign up free
2. Go to "Files" → upload `app.py`, `requirements.txt`, and the `templates/` folder
3. Go to "Web" → Add new web app → Flask → Python 3.11
4. Set source code to `/home/yourusername/`
5. Click Reload → your app is live at `yourusername.pythonanywhere.com`

### Option B — Render.com (Free, GitHub)
1. Push this folder to GitHub
2. Go to https://render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Free tier gives you a live URL

---

## 🔑 DEFAULT PASSWORDS

| Role        | Username | Password  |
|-------------|----------|-----------|
| Admin       | admin    | admin     |
| Coordinator | coord    | coord     |
| Ravi Kumar  | —        | ravi123   |
| Priya Mehra | —        | priya123  |
| Sahil Verma | —        | sahil123  |

---

## 💾 DATABASE

All data is stored in `nitya_vfx.db` (SQLite file in same folder as app.py).
- **Back it up regularly** — just copy this file
- Never delete it — it has all your projects, time logs, salary data

## 📁 PROJECT STRUCTURE

```
nitya_vfx/
├── app.py              ← Main server (run this)
├── requirements.txt    ← Python packages needed
├── nitya_vfx.db        ← Database (auto-created on first run)
├── README.md           ← This file
└── templates/
    └── index.html      ← Frontend (the portal UI)
```
