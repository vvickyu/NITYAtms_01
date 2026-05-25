"""
Nitya VFX Studio — Backend Server
Flask + SQLite — All data persisted in nitya_vfx.db
Run: python app.py
"""

from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
import sqlite3, json, os, datetime

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), 'nitya_vfx.db')


# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    -- Projects
    CREATE TABLE IF NOT EXISTS projects (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        client    TEXT,
        start_date TEXT,
        deadline  TEXT,
        budget    REAL DEFAULT 0,
        desc      TEXT,
        status    TEXT DEFAULT 'Active'
    );

    -- Artists (users)
    CREATE TABLE IF NOT EXISTS artists (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        role      TEXT,
        rate      REAL DEFAULT 0,
        password  TEXT NOT NULL,
        rate_from TEXT
    );

    -- Rate history (when admin changes artist rate)
    CREATE TABLE IF NOT EXISTS rate_history (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        artist_id INTEGER REFERENCES artists(id) ON DELETE CASCADE,
        old_rate  REAL,
        from_date TEXT,
        to_date   TEXT
    );

    -- Shot assignments (many-to-many: artists <-> shots)
    CREATE TABLE IF NOT EXISTS artist_shots (
        artist_id INTEGER REFERENCES artists(id) ON DELETE CASCADE,
        shot_id   INTEGER REFERENCES shots(id)   ON DELETE CASCADE,
        PRIMARY KEY (artist_id, shot_id)
    );

    -- Shots
    CREATE TABLE IF NOT EXISTS shots (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        task        TEXT,
        frames      INTEGER DEFAULT 0,
        status      TEXT DEFAULT 'Not Started',
        est_hours   REAL DEFAULT 0,
        outsourced  INTEGER DEFAULT 0
    );

    -- Outsource entries
    CREATE TABLE IF NOT EXISTS outsource (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shot_id       INTEGER REFERENCES shots(id) ON DELETE CASCADE,
        vendor        TEXT,
        cost          REAL DEFAULT 0,
        delivery_date TEXT,
        status        TEXT DEFAULT 'Pending'
    );

    -- Time logs
    CREATE TABLE IF NOT EXISTS time_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        artist_id   INTEGER REFERENCES artists(id) ON DELETE CASCADE,
        shot_id     INTEGER REFERENCES shots(id)   ON DELETE CASCADE,
        log_date    TEXT NOT NULL,
        duration_ms INTEGER DEFAULT 0,
        note        TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- Vendor payments
    CREATE TABLE IF NOT EXISTS payments (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor       TEXT NOT NULL,
        amount       REAL DEFAULT 0,
        pay_month    TEXT,
        project_id   INTEGER,
        project_name TEXT,
        pct          REAL DEFAULT 100,
        note         TEXT,
        pay_date     TEXT DEFAULT (date('now'))
    );

    -- Invoices
    CREATE TABLE IF NOT EXISTS invoices (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        inv_no       TEXT UNIQUE,
        project_id   INTEGER,
        inv_date     TEXT,
        due_date     TEXT,
        inv_month    TEXT,
        pct          REAL DEFAULT 100,
        studio       TEXT DEFAULT 'Nitya VFX Studio',
        amount       REAL DEFAULT 0,
        paid_amount  REAL DEFAULT 0,
        notes        TEXT,
        status       TEXT DEFAULT 'Unpaid'
    );

    -- Shot file links (Google Drive / Dropbox)
    CREATE TABLE IF NOT EXISTS shot_files (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        shot_id          INTEGER REFERENCES shots(id) ON DELETE CASCADE,
        version          TEXT,
        name             TEXT,
        link             TEXT,
        note             TEXT,
        uploaded_by      TEXT,
        uploaded_by_role TEXT,
        ts               INTEGER
    );

    -- Shot correction logs
    CREATE TABLE IF NOT EXISTS shot_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        shot_id    INTEGER REFERENCES shots(id) ON DELETE CASCADE,
        by_name    TEXT,
        by_role    TEXT,
        log_text   TEXT,
        screenshot TEXT,
        ts         INTEGER
    );

    -- Admin credentials (single row)
    CREATE TABLE IF NOT EXISTS admin_creds (
        id       INTEGER PRIMARY KEY,
        username TEXT DEFAULT 'admin',
        password TEXT DEFAULT 'admin'
    );

    -- Coordinator credentials
    CREATE TABLE IF NOT EXISTS coord_creds (
        id       INTEGER PRIMARY KEY,
        username TEXT DEFAULT 'coord',
        password TEXT DEFAULT 'coord'
    );
    """)

    # Seed admin/coord if empty
    c.execute("INSERT OR IGNORE INTO admin_creds (id,username,password) VALUES (1,'admin','admin')")
    c.execute("INSERT OR IGNORE INTO coord_creds (id,username,password) VALUES (1,'coord','coord')")

    # Seed sample projects if empty
    c.execute("SELECT COUNT(*) FROM projects")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO projects (name,client,deadline,budget,desc,status) VALUES (?,?,?,?,?,?)", [
            ('Project Aurora','Netflix India','2025-08-30',500000,'High-end VFX for feature film.','Active'),
            ('Project Nebula','Amazon Prime','2025-07-15',300000,'Series VFX work.','Active'),
            ('Project Comet','Hotstar','2025-09-20',200000,'Short film VFX.','Active'),
        ])
        c.executemany("INSERT INTO artists (name,role,rate,password) VALUES (?,?,?,?)", [
            ('Ravi Kumar','VFX Artist',312,'ravi123'),
            ('Priya Mehra','Compositor',375,'priya123'),
            ('Sahil Verma','Rotoscoper',250,'sahil123'),
        ])
        c.executemany("INSERT INTO shots (project_id,name,status,est_hours,outsourced) VALUES (?,?,?,?,0)", [
            (1,'SH_0010','In Progress',8),
            (1,'SH_0020','Not Started',12),
            (2,'SH_0030','In Progress',6),
            (2,'SH_0040','Review',10),
            (3,'SH_0050','Not Started',5),
        ])
        # Assign shots to artists
        c.executemany("INSERT OR IGNORE INTO artist_shots (artist_id,shot_id) VALUES (?,?)", [
            (1,1),(1,2),(2,3),(3,4),(3,5)
        ])

    conn.commit()
    conn.close()
    print("✅ Database ready:", DB_PATH)


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

def today():
    return datetime.date.today().isoformat()


# ─────────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')


# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    role = data.get('role')
    username = data.get('username','').strip()
    password = data.get('password','').strip()

    conn = get_db()
    c = conn.cursor()

    if role == 'admin':
        c.execute("SELECT * FROM admin_creds WHERE id=1")
        cred = c.fetchone()
        conn.close()
        if cred and cred['username']==username and cred['password']==password:
            return jsonify({'ok':True,'role':'admin'})
        return jsonify({'ok':False,'error':'Wrong username or password'})

    elif role == 'coord':
        c.execute("SELECT * FROM coord_creds WHERE id=1")
        cred = c.fetchone()
        conn.close()
        if cred and cred['username']==username and cred['password']==password:
            return jsonify({'ok':True,'role':'coord'})
        return jsonify({'ok':False,'error':'Wrong username or password'})

    elif role == 'artist':
        artist_id = data.get('artist_id')
        c.execute("SELECT * FROM artists WHERE id=?", (artist_id,))
        artist = c.fetchone()
        conn.close()
        if artist and artist['password']==password:
            return jsonify({'ok':True,'role':'artist','artist':row_to_dict(artist)})
        return jsonify({'ok':False,'error':'Wrong password'})

    conn.close()
    return jsonify({'ok':False,'error':'Unknown role'})


# ─────────────────────────────────────────
# PROJECTS
# ─────────────────────────────────────────

@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route('/api/projects', methods=['POST'])
def add_project():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO projects (name,client,start_date,deadline,budget,desc,status) VALUES (?,?,?,?,?,?,?)",
        (d.get('name'),d.get('client'),d.get('startDate'),d.get('deadline'),
         d.get('budget',0),d.get('desc'),d.get('status','Active'))
    )
    pid = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':pid})

@app.route('/api/projects/<int:pid>', methods=['PUT'])
def update_project(pid):
    d = request.json
    conn = get_db()
    conn.execute(
        "UPDATE projects SET name=?,client=?,start_date=?,deadline=?,budget=?,desc=?,status=? WHERE id=?",
        (d.get('name'),d.get('client'),d.get('startDate'),d.get('deadline'),
         d.get('budget',0),d.get('desc'),d.get('status','Active'),pid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/projects/<int:pid>', methods=['DELETE'])
def delete_project(pid):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# ARTISTS
# ─────────────────────────────────────────

@app.route('/api/artists', methods=['GET'])
def get_artists():
    conn = get_db()
    artists = rows_to_list(conn.execute("SELECT * FROM artists ORDER BY id").fetchall())
    for a in artists:
        rows = conn.execute("SELECT shot_id FROM artist_shots WHERE artist_id=?", (a['id'],)).fetchall()
        a['shotIds'] = [r['shot_id'] for r in rows]
    conn.close()
    return jsonify(artists)

@app.route('/api/artists', methods=['POST'])
def add_artist():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO artists (name,role,rate,password) VALUES (?,?,?,?)",
        (d.get('name'),d.get('role','Artist'),d.get('rate',0),d.get('password',''))
    )
    aid = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':aid})

@app.route('/api/artists/<int:aid>', methods=['PUT'])
def update_artist(aid):
    d = request.json
    conn = get_db()
    if 'rate' in d:
        # Save rate history
        old = conn.execute("SELECT rate,rate_from FROM artists WHERE id=?", (aid,)).fetchone()
        if old and old['rate'] != d['rate']:
            conn.execute(
                "INSERT INTO rate_history (artist_id,old_rate,from_date,to_date) VALUES (?,?,?,?)",
                (aid, old['rate'], old['rate_from'] or today(), today())
            )
        conn.execute(
            "UPDATE artists SET name=?,role=?,rate=?,rate_from=? WHERE id=?",
            (d.get('name'),d.get('role'),d.get('rate'),today(),aid)
        )
    else:
        conn.execute(
            "UPDATE artists SET name=?,role=? WHERE id=?",
            (d.get('name'),d.get('role'),aid)
        )
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/artists/<int:aid>', methods=['DELETE'])
def delete_artist(aid):
    conn = get_db()
    conn.execute("DELETE FROM artists WHERE id=?", (aid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/artists/<int:aid>/shots', methods=['PUT'])
def update_artist_shots(aid):
    d = request.json
    shot_ids = d.get('shotIds', [])
    conn = get_db()
    conn.execute("DELETE FROM artist_shots WHERE artist_id=?", (aid,))
    for sid in shot_ids:
        conn.execute("INSERT OR IGNORE INTO artist_shots (artist_id,shot_id) VALUES (?,?)", (aid,sid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/artists/<int:aid>/assign_shot', methods=['POST'])
def assign_shot_to_artist(aid):
    d = request.json
    sid = d.get('shot_id')
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO artist_shots (artist_id,shot_id) VALUES (?,?)", (aid,sid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# SHOTS
# ─────────────────────────────────────────

@app.route('/api/shots', methods=['GET'])
def get_shots():
    conn = get_db()
    shots = rows_to_list(conn.execute("SELECT * FROM shots ORDER BY id").fetchall())
    conn.close()
    return jsonify(shots)

@app.route('/api/shots', methods=['POST'])
def add_shot():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO shots (project_id,name,task,frames,status,est_hours,outsourced) VALUES (?,?,?,?,?,?,?)",
        (d.get('projectId'),d.get('name'),d.get('task',''),d.get('frames',0),
         d.get('status','Not Started'),d.get('estHours',0),0)
    )
    sid = cur.lastrowid
    # Auto-assign artist if provided
    if d.get('artistId'):
        conn.execute("INSERT OR IGNORE INTO artist_shots (artist_id,shot_id) VALUES (?,?)",
                     (d['artistId'], sid))
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':sid})

@app.route('/api/shots/bulk', methods=['POST'])
def add_shots_bulk():
    """Import multiple shots at once (Excel import)"""
    d = request.json
    project_id = d.get('projectId')
    shots_data = d.get('shots', [])
    conn = get_db()
    ids = []
    for s in shots_data:
        cur = conn.execute(
            "INSERT INTO shots (project_id,name,task,frames,status,est_hours,outsourced) VALUES (?,?,?,?,?,?,?)",
            (project_id, s.get('name'), s.get('task',''), s.get('frames',0),
             'Not Started', s.get('estHours',0), 0)
        )
        sid = cur.lastrowid
        ids.append(sid)
        if s.get('artistName'):
            artist = conn.execute("SELECT id FROM artists WHERE LOWER(name)=LOWER(?)", (s['artistName'],)).fetchone()
            if artist:
                conn.execute("INSERT OR IGNORE INTO artist_shots (artist_id,shot_id) VALUES (?,?)",
                             (artist['id'], sid))
    conn.commit(); conn.close()
    return jsonify({'ok':True,'ids':ids,'count':len(ids)})

@app.route('/api/shots/<int:sid>', methods=['PUT'])
def update_shot(sid):
    d = request.json
    conn = get_db()
    conn.execute(
        "UPDATE shots SET name=?,task=?,frames=?,status=?,est_hours=?,outsourced=?,project_id=? WHERE id=?",
        (d.get('name'),d.get('task',''),d.get('frames',0),d.get('status'),
         d.get('estHours',0),1 if d.get('outsourced') else 0,d.get('projectId'),sid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/shots/<int:sid>/status', methods=['PUT'])
def update_shot_status(sid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE shots SET status=? WHERE id=?", (d.get('status'), sid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/shots/<int:sid>', methods=['DELETE'])
def delete_shot(sid):
    conn = get_db()
    conn.execute("DELETE FROM shots WHERE id=?", (sid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# OUTSOURCE
# ─────────────────────────────────────────

@app.route('/api/outsource', methods=['GET'])
def get_outsource():
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM outsource ORDER BY id").fetchall())
    conn.close()
    return jsonify(rows)

@app.route('/api/outsource', methods=['POST'])
def add_outsource():
    d = request.json
    conn = get_db()
    # Mark shot as outsourced
    conn.execute("UPDATE shots SET outsourced=1 WHERE id=?", (d.get('shotId'),))
    # Upsert outsource entry
    existing = conn.execute("SELECT id FROM outsource WHERE shot_id=?", (d.get('shotId'),)).fetchone()
    if existing:
        conn.execute(
            "UPDATE outsource SET vendor=?,cost=?,delivery_date=?,status=? WHERE shot_id=?",
            (d.get('vendor'),d.get('cost',0),d.get('deliveryDate'),d.get('status','Pending'),d.get('shotId'))
        )
        oid = existing['id']
    else:
        cur = conn.execute(
            "INSERT INTO outsource (shot_id,vendor,cost,delivery_date,status) VALUES (?,?,?,?,?)",
            (d.get('shotId'),d.get('vendor'),d.get('cost',0),d.get('deliveryDate'),'Pending')
        )
        oid = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':oid})

@app.route('/api/outsource/<int:oid>', methods=['PUT'])
def update_outsource(oid):
    d = request.json
    conn = get_db()
    conn.execute(
        "UPDATE outsource SET vendor=?,cost=?,delivery_date=?,status=? WHERE id=?",
        (d.get('vendor'),d.get('cost',0),d.get('deliveryDate'),d.get('status'),oid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/outsource/<int:oid>', methods=['DELETE'])
def delete_outsource(oid):
    conn = get_db()
    o = conn.execute("SELECT shot_id FROM outsource WHERE id=?", (oid,)).fetchone()
    if o:
        conn.execute("UPDATE shots SET outsourced=0 WHERE id=?", (o['shot_id'],))
    conn.execute("DELETE FROM outsource WHERE id=?", (oid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# TIME LOGS
# ─────────────────────────────────────────

@app.route('/api/timelogs', methods=['GET'])
def get_timelogs():
    """Returns all time logs grouped as {artist_id: {date: {shot_id: [{durationMs,note}]}}}"""
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM time_logs ORDER BY id").fetchall())
    conn.close()
    # Build nested structure matching frontend DB.timeLogs
    result = {}
    for r in rows:
        aid = str(r['artist_id'])
        date = r['log_date']
        sid = str(r['shot_id'])
        if aid not in result: result[aid] = {}
        if date not in result[aid]: result[aid][date] = {}
        if sid not in result[aid][date]: result[aid][date][sid] = []
        result[aid][date][sid].append({'durationMs': r['duration_ms'], 'note': r['note'] or ''})
    return jsonify(result)

@app.route('/api/timelogs', methods=['POST'])
def add_timelog():
    d = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO time_logs (artist_id,shot_id,log_date,duration_ms,note) VALUES (?,?,?,?,?)",
        (d.get('artistId'), d.get('shotId'), d.get('date', today()),
         d.get('durationMs', 0), d.get('note',''))
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/timelogs/bulk', methods=['POST'])
def bulk_timelogs():
    """Save full time log state from frontend after timer stops"""
    d = request.json
    artist_id = d.get('artistId')
    shot_id = d.get('shotId')
    log_date = d.get('date', today())
    duration_ms = d.get('durationMs', 0)
    note = d.get('note', '')
    conn = get_db()
    conn.execute(
        "INSERT INTO time_logs (artist_id,shot_id,log_date,duration_ms,note) VALUES (?,?,?,?,?)",
        (artist_id, shot_id, log_date, duration_ms, note)
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# PAYMENTS (Outsource Vendor Payments)
# ─────────────────────────────────────────

@app.route('/api/payments', methods=['GET'])
def get_payments():
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM payments ORDER BY id").fetchall())
    conn.close()
    return jsonify(rows)

@app.route('/api/payments', methods=['POST'])
def add_payment():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO payments (vendor,amount,pay_month,project_id,project_name,pct,note,pay_date) VALUES (?,?,?,?,?,?,?,?)",
        (d.get('vendor'),d.get('amount',0),d.get('month'),d.get('projectId'),
         d.get('projectName'),d.get('pct',100),d.get('note'),today())
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':cur.lastrowid})

@app.route('/api/payments/<int:pid>', methods=['DELETE'])
def delete_payment(pid):
    conn = get_db()
    conn.execute("DELETE FROM payments WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# INVOICES
# ─────────────────────────────────────────

@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    conn = get_db()
    rows = rows_to_list(conn.execute("SELECT * FROM invoices ORDER BY id").fetchall())
    conn.close()
    return jsonify(rows)

@app.route('/api/invoices', methods=['POST'])
def add_invoice():
    d = request.json
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO invoices (inv_no,project_id,inv_date,due_date,inv_month,pct,studio,amount,paid_amount,notes,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (d.get('invNo'),d.get('projectId'),d.get('date'),d.get('due'),d.get('month'),
             d.get('pct',100),d.get('studio','Nitya VFX Studio'),d.get('amount',0),
             d.get('paidAmount',0),d.get('notes'),'Unpaid')
        )
        conn.commit(); conn.close()
        return jsonify({'ok':True,'id':cur.lastrowid})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'ok':False,'error':'Invoice number already exists'})

@app.route('/api/invoices/<int:iid>', methods=['PUT'])
def update_invoice(iid):
    d = request.json
    conn = get_db()
    conn.execute(
        "UPDATE invoices SET paid_amount=?,status=? WHERE id=?",
        (d.get('paidAmount',0), d.get('status','Unpaid'), iid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/invoices/<int:iid>', methods=['DELETE'])
def delete_invoice(iid):
    conn = get_db()
    conn.execute("DELETE FROM invoices WHERE id=?", (iid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# SHOT FILES (links)
# ─────────────────────────────────────────

@app.route('/api/shot_files/<int:sid>', methods=['GET'])
def get_shot_files(sid):
    conn = get_db()
    rows = rows_to_list(conn.execute(
        "SELECT * FROM shot_files WHERE shot_id=? ORDER BY ts DESC", (sid,)).fetchall())
    conn.close()
    return jsonify(rows)

@app.route('/api/shot_files', methods=['POST'])
def add_shot_file():
    d = request.json
    import time
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO shot_files (shot_id,version,name,link,note,uploaded_by,uploaded_by_role,ts) VALUES (?,?,?,?,?,?,?,?)",
        (d.get('shotId'),d.get('version'),d.get('name'),d.get('link'),
         d.get('note'),d.get('uploadedBy'),d.get('uploadedByRole'),
         d.get('ts', int(time.time()*1000)))
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':cur.lastrowid})

@app.route('/api/shot_files/<int:fid>', methods=['DELETE'])
def delete_shot_file(fid):
    conn = get_db()
    conn.execute("DELETE FROM shot_files WHERE id=?", (fid,))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# SHOT LOGS (correction notes)
# ─────────────────────────────────────────

@app.route('/api/shot_logs/<int:sid>', methods=['GET'])
def get_shot_logs(sid):
    conn = get_db()
    rows = rows_to_list(conn.execute(
        "SELECT * FROM shot_logs WHERE shot_id=? ORDER BY ts DESC", (sid,)).fetchall())
    conn.close()
    return jsonify(rows)

@app.route('/api/shot_logs', methods=['POST'])
def add_shot_log():
    d = request.json
    import time
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO shot_logs (shot_id,by_name,by_role,log_text,screenshot,ts) VALUES (?,?,?,?,?,?)",
        (d.get('shotId'),d.get('by'),d.get('byRole'),d.get('text'),
         d.get('screenshot'), d.get('ts', int(time.time()*1000)))
    )
    conn.commit(); conn.close()
    return jsonify({'ok':True,'id':cur.lastrowid})


# ─────────────────────────────────────────
# ADMIN SETTINGS (change passwords)
# ─────────────────────────────────────────

@app.route('/api/settings/admin', methods=['PUT'])
def update_admin_creds():
    d = request.json
    conn = get_db()
    conn.execute("UPDATE admin_creds SET username=?,password=? WHERE id=1",
                 (d.get('username','admin'), d.get('password','admin')))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/settings/coord', methods=['PUT'])
def update_coord_creds():
    d = request.json
    conn = get_db()
    conn.execute("UPDATE coord_creds SET username=?,password=? WHERE id=1",
                 (d.get('username','coord'), d.get('password','coord')))
    conn.commit(); conn.close()
    return jsonify({'ok':True})

@app.route('/api/artists/<int:aid>/password', methods=['PUT'])
def update_artist_password(aid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE artists SET password=? WHERE id=?", (d.get('password'), aid))
    conn.commit(); conn.close()
    return jsonify({'ok':True})


# ─────────────────────────────────────────
# FULL DATA SNAPSHOT (for initial load)
# ─────────────────────────────────────────

@app.route('/api/snapshot', methods=['GET'])
def snapshot():
    """Returns all data in one call — used by frontend on startup"""
    conn = get_db()

    projects = rows_to_list(conn.execute("SELECT * FROM projects ORDER BY id").fetchall())
    artists  = rows_to_list(conn.execute("SELECT * FROM artists ORDER BY id").fetchall())
    shots    = rows_to_list(conn.execute("SELECT * FROM shots ORDER BY id").fetchall())
    outsource= rows_to_list(conn.execute("SELECT * FROM outsource ORDER BY id").fetchall())
    payments = rows_to_list(conn.execute("SELECT * FROM payments ORDER BY id").fetchall())
    invoices = rows_to_list(conn.execute("SELECT * FROM invoices ORDER BY id").fetchall())
    s_files  = rows_to_list(conn.execute("SELECT * FROM shot_files ORDER BY ts DESC").fetchall())
    s_logs   = rows_to_list(conn.execute("SELECT * FROM shot_logs ORDER BY ts DESC").fetchall())
    t_logs   = rows_to_list(conn.execute("SELECT * FROM time_logs ORDER BY id").fetchall())
    a_shots  = rows_to_list(conn.execute("SELECT * FROM artist_shots").fetchall())
    admin_c  = row_to_dict(conn.execute("SELECT username FROM admin_creds WHERE id=1").fetchone())
    coord_c  = row_to_dict(conn.execute("SELECT username FROM coord_creds WHERE id=1").fetchone())
    conn.close()

    # Attach shotIds to artists
    shot_map = {}
    for r in a_shots:
        shot_map.setdefault(r['artist_id'], []).append(r['shot_id'])
    for a in artists:
        a['shotIds'] = shot_map.get(a['id'], [])

    # Build time logs nested structure
    time_log_nested = {}
    for r in t_logs:
        aid = str(r['artist_id']); date = r['log_date']; sid = str(r['shot_id'])
        time_log_nested.setdefault(aid, {}).setdefault(date, {}).setdefault(sid, []).append(
            {'durationMs': r['duration_ms'], 'note': r['note'] or ''})

    # Group shot files by shot_id
    shot_files_map = {}
    for f in s_files:
        shot_files_map.setdefault(str(f['shot_id']), []).append(f)

    # Group shot logs by shot_id
    shot_logs_map = {}
    for l in s_logs:
        shot_logs_map.setdefault(str(l['shot_id']), []).append(l)

    return jsonify({
        'projects':  projects,
        'artists':   artists,
        'shots':     shots,
        'outsource': outsource,
        'payments':  payments,
        'invoices':  invoices,
        'timeLogs':  time_log_nested,
        'shotFiles': shot_files_map,
        'shotLogs':  shot_logs_map,
        'adminUsername': admin_c['username'] if admin_c else 'admin',
        'coordUsername': coord_c['username'] if coord_c else 'coord',
    })


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("🎬 Nitya VFX Studio server starting...")
    print("🌐 Open: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
