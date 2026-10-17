"""Durable, unique-reel timings; no historical inference from updated timestamps."""
import statistics
import time

TERMINAL = ('ready', 'review', 'failed')


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS processing_runs(
            batch_id INTEGER PRIMARY KEY, started REAL NOT NULL, finished REAL);
        CREATE TABLE IF NOT EXISTS processing_timings(
            batch_id INTEGER NOT NULL, reel_id TEXT NOT NULL,
            started REAL NOT NULL, finished REAL, outcome TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(batch_id,reel_id),
            FOREIGN KEY(reel_id) REFERENCES reels(id) ON DELETE CASCADE);
    ''')


def claim(db, batch, rid, now=None):
    now = time.time() if now is None else now
    db.execute('INSERT OR IGNORE INTO processing_runs VALUES(?,?,NULL)', (batch, now))
    db.execute('UPDATE processing_runs SET finished=NULL WHERE batch_id=?', (batch,))
    db.execute('''INSERT INTO processing_timings VALUES(?,?,?,NULL,'')
        ON CONFLICT(batch_id,reel_id) DO UPDATE SET finished=NULL,outcome='' ''', (batch, rid, now))


def finish(db, rid, now=None):
    """Called in the result transaction; retries retain the first claim time."""
    now = time.time() if now is None else now
    row = db.execute('SELECT status,analysis FROM reels WHERE id=?', (rid,)).fetchone()
    if not row or row['status'] not in TERMINAL:
        return
    outcome = row['status']
    if outcome == 'ready':
        assigned = db.execute('SELECT 1 FROM reel_boxes WHERE reel_id=? LIMIT 1', (rid,)).fetchone()
        outcome = 'organized' if assigned and row['analysis'] else 'review'
    timing = db.execute('SELECT batch_id FROM processing_timings WHERE reel_id=? AND finished IS NULL', (rid,)).fetchall()
    db.execute('UPDATE processing_timings SET finished=?,outcome=? WHERE reel_id=? AND finished IS NULL', (now, outcome, rid))
    config = dict(db.execute('SELECT key,value FROM settings'))
    for item in timing:
        batch = item['batch_id']
        active = db.execute('SELECT 1 FROM processing_timings WHERE batch_id=? AND finished IS NULL', (batch,)).fetchone()
        used = db.execute('SELECT count(*) FROM processing_batch_items WHERE batch_id=?', (batch,)).fetchone()[0]
        size = int(config['batch_size'])
        eligible = db.execute("SELECT 1 FROM reels WHERE status IN ('queued','waiting_model') AND info_only='' LIMIT 1").fetchone()
        if not active and (not eligible or (size and used >= size)):
            db.execute('UPDATE processing_runs SET finished=? WHERE batch_id=?', (now, batch))


def summary(db, batch, now=None):
    now = time.time() if now is None else now
    run = db.execute('SELECT * FROM processing_runs WHERE batch_id=?', (batch,)).fetchone()
    rows = db.execute('SELECT * FROM processing_timings WHERE batch_id=?', (batch,)).fetchall()
    success = [r for r in rows if r['outcome'] == 'organized']
    elapsed = max(0, (run['finished'] or now) - run['started']) if run else None
    durations = [max(0, r['finished'] - r['started']) for r in success]
    return {
        'batch_id': batch, 'measured': bool(run), 'started_at': run['started'] if run else None,
        'finished_at': run['finished'] if run else None, 'tracked': len(rows),
        'organized': len(success), 'review': sum(r['outcome'] == 'review' for r in rows),
        'errors': sum(r['outcome'] == 'failed' for r in rows),
        'elapsed_seconds': elapsed,
        'reels_per_minute': len(success) * 60 / elapsed if success and elapsed else None,
        'median_seconds': statistics.median(durations) if durations else None,
        'timing_basis': 'Wall time from first claim; includes pauses, retries and model waits.',
    }


def board(db, data, batch):
    """Bounded global board, independent of library filters and pagination."""
    from pathlib import Path
    counts = dict(db.execute('SELECT status,count(*) FROM reels GROUP BY status'))
    ready = db.execute("SELECT count(*) FROM reels r WHERE status='ready' AND analysis IS NOT NULL AND EXISTS(SELECT 1 FROM reel_boxes WHERE reel_id=r.id)").fetchone()[0]
    def cards(where, order, limit):
        result = []
        for row in db.execute('SELECT r.* FROM reels r WHERE ' + where + ' ORDER BY ' + order + ' LIMIT ?', (limit,)):
            folders = [dict(b) for b in db.execute('SELECT b.id,b.name FROM boxes b JOIN reel_boxes rb ON rb.box_id=b.id WHERE rb.reel_id=? ORDER BY b.id', (row['id'],))]
            result.append({'id': row['id'], 'title': row['title'] or row['source_title'] or 'Saved reel',
                           'status': row['status'], 'boxes': folders,
                           'thumbnail': '/thumbnails/' + row['id'] + '.jpg' if (Path(data) / 'thumbnails' / (row['id'] + '.jpg')).is_file() else None})
        return result
    return {
        'counts': {'unorganized': counts.get('queued', 0),
                   'organizing': sum(n for s, n in counts.items() if s not in (*TERMINAL, 'queued', 'waiting_model')),
                   'organized': ready, 'review': counts.get('review', 0) + counts.get('ready', 0) - ready,
                   'waiting': counts.get('waiting_model', 0), 'errors': counts.get('failed', 0)},
        'unorganized': cards("status='queued'", 'scan_started DESC,saved_position,created', 20),
        'organizing': cards("status NOT IN ('ready','review','failed','queued','waiting_model')", 'updated', 5),
        'organized': cards("status='ready' AND analysis IS NOT NULL AND EXISTS(SELECT 1 FROM reel_boxes WHERE reel_id=r.id)", 'updated DESC', 20),
    }
