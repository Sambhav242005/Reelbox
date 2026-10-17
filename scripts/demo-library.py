"""Prepare an isolated real-evidence sample, serve it, and report measured results.

Never copies credentials or writes to the source library. All private artifacts
live under work/demo (ignored). No Instagram or video network calls are allowed.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'demo'
ALLOWED_TOPICS = ('AI', 'Code', 'Technology', 'Useful Projects', 'UI')
EXCLUDED_CONTENT = re.compile(r'\b(manga|manhwa|manhua|anime|webtoons?|waifu|minecraft|genshin|honkai|otaku|gaming|games?|gamer|pokemon)\b', re.I)
TECH_CONTENT = re.compile(r'\b(github|gitlab|coding|code|programming|software|developer|python|javascript|typescript|react|css|html|api|llm|ai|agents?|tech|technology|apps?|repository|repositories|repo|open.source|computer|linux|windows|automation|chatgpt|claude|gemini|ollama|database|web|website|frontend|backend|ui|ux)\b', re.I)
sys.path.insert(0, str(ROOT / 'app'))
import app


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def fingerprint(db):
    digest = hashlib.sha256()
    for table in ('reels', 'boxes', 'reel_boxes', 'settings'):
        for row in db.execute('SELECT * FROM ' + table + ' ORDER BY 1'):
            digest.update(json.dumps(list(row), ensure_ascii=False).encode())
    return digest.hexdigest()


def prepare(source):
    if WORK.exists():
        raise SystemExit('work/demo exists. Archive it before preparing a new measurement.')
    source = source.resolve()
    db = sqlite3.connect((source / 'library.sqlite').as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    baseline = fingerprint(db)
    selected, used, groups, extras = [], set(), [], []
    topics = db.execute("SELECT b.*,count(*) n FROM boxes b JOIN reel_boxes rb ON rb.box_id=b.id JOIN reels r ON r.id=rb.reel_id WHERE r.status='ready' GROUP BY b.id ORDER BY n DESC,b.id").fetchall()
    for box in topics:
        if box['name'] not in ALLOWED_TOPICS:
            continue
        candidates = db.execute("SELECT r.id,r.url,r.source_title,r.caption,r.creator FROM reels r JOIN reel_boxes rb ON rb.reel_id=r.id WHERE rb.box_id=? AND r.status='ready' ORDER BY r.scan_started DESC,r.saved_position,r.created,r.rowid", (box['id'],)).fetchall()
        eligible = []
        for row in candidates:
            if row['id'] in used or not all(str(row[k] or '').strip() for k in ('source_title', 'caption', 'creator')):
                continue
            text = row['source_title'] + ' ' + row['caption']
            excluded_folder = db.execute("SELECT 1 FROM reel_boxes rb JOIN boxes b ON b.id=rb.box_id WHERE rb.reel_id=? AND b.name IN ('Anime','Manhwa','Gaming')", (row['id'],)).fetchone()
            if excluded_folder or EXCLUDED_CONTENT.search(text) or not TECH_CONTENT.search(text):
                continue
            cover = source / 'thumbnails' / (row['id'] + '.jpg')
            if not cover.is_file():
                continue
            probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', str(cover)], capture_output=True, text=True)
            if probe.returncode or not json.loads(probe.stdout).get('streams'):
                continue
            eligible.append(dict(row))
            if len(eligible) >= 12:
                break
        if len(eligible) < 10:
            continue
        group = eligible[:10]
        used.update(r['id'] for r in group)
        groups.append({'id': box['id'], 'name': box['name'], 'description': box['description'], 'reels': group})
        extras.extend(eligible[10:])
        if len(groups) == 5:
            break
    if len(groups) != 5:
        raise SystemExit('Need five permitted technology topics with ten distinct complete, readable-cover reels each.')
    # First 20 are the showcase, four per topic. All 50 are processed.
    selected = [r for g in groups for r in g['reels'][:4]] + [r for g in groups for r in g['reels'][4:]]
    warm = [r for r in extras if r['id'] not in used][:2]
    if len(warm) != 2:
        raise SystemExit('Need two warm-up examples outside the sample.')
    WORK.mkdir(parents=True)
    for name, records in (('library', selected), ('warmup', warm)):
        app.DATA = WORK / name
        app.initialize()
        with app.connect() as dest:
            for group in groups:
                dest.execute('INSERT INTO boxes(id,name,description,embedding) VALUES(?,?,?,?)', (group['id'], group['name'], group['description'], '[]'))
        for index, row in enumerate(records):
            app.enqueue([{'url': row['url'], 'title': row['source_title'], 'caption': row['caption'], 'creator': row['creator'], 'scan_started': 100, 'saved_position': index}])
            shutil.copy2(source / 'thumbnails' / (row['id'] + '.jpg'), app.DATA / 'thumbnails' / (row['id'] + '.jpg'))
            with app.connect() as dest:
                dest.execute('UPDATE reels SET refresh_analysis=1,metadata_checked=1 WHERE id=?', (row['id'],))
        app.configure_processing('stop')
    manifest = {'source': str(source), 'source_fingerprint': baseline,
                'showcase_ids': [r['id'] for r in selected[:20]], 'sample_ids': [r['id'] for r in selected],
                'topics': [{'name': g['name'], 'count': 10} for g in groups],
                'warmup_ids': [r['id'] for r in warm], 'size': 50,
                'content_policy': 'GitHub, AI, coding and technology only; exclude manga, manhwa, anime and gaming in source text or folder memberships.',
                'scope': 'Cached captions + covers · fresh local AI · Instagram retrieval excluded.'}
    write_json(WORK / 'manifest.json', manifest)
    db.close()
    print('Prepared 50 real reels (20 showcase) and 2 separate warm-ups; source opened read-only.', flush=True)


def block_source(*args, **kwargs):
    raise RuntimeError('Demo guard: Instagram retrieval and video downloads are disabled.')


def serve(port, skip_warmup=False):
    manifest = read_json(WORK / 'manifest.json')
    if urlparse(app.model_client.BASE).hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise SystemExit('Demo requires a local model endpoint.')
    if any('cloud' in m for m in (app.MODEL, app.DECISION_MODEL, app.EMBED_MODEL)):
        raise SystemExit('Demo requires local models.')
    app.metadata = app.download = app.acquire_cover = block_source
    # Cached evidence must already be complete; no accidental source traffic.
    app.instagram_source.resolve = app.instagram_source.download_video = block_source
    if not skip_warmup:
        app.DATA = WORK / 'warmup'
        app.initialize()
        app.configure_processing('resume')
        print('Warming local models with two excluded examples...', flush=True)
        for _ in range(2):
            if not app.worker_step():
                raise RuntimeError('Warm-up cannot start; check local models.')
        with app.connect() as db:
            print('Warm-up outcomes:', list(map(tuple, db.execute('SELECT status,count(*) FROM reels GROUP BY status'))), flush=True)
        write_json(WORK / 'warmup-complete.json', {'completed_at': time.time(), 'excluded': True})
    elif not (WORK / 'warmup-complete.json').exists():
        raise SystemExit('--skip-warmup requires a completed warm-up in this sample.')
    app.DATA = WORK / 'library'
    app.PORT = port
    app.initialize()
    with app.connect() as db:
        folders = db.execute('SELECT id,name,description FROM boxes').fetchall()
    for folder in folders:
        vector = app.embed(folder['name'] + ' ' + folder['description'])
        with app.connect() as db:
            db.execute('UPDATE boxes SET embedding=? WHERE id=?', (json.dumps(vector), folder['id']))
    with app.connect() as db:
        if db.execute('SELECT count(*) FROM processing_runs').fetchone()[0]:
            raise SystemExit('This sample has already started. Refusing to repeat its benchmark.')
        db.execute('DELETE FROM inference_cache')
    server = app.ThreadingHTTPServer(('127.0.0.1', port), app.Handler)
    for i in range(app.QUEUE_WINDOW):
        threading.Thread(target=app.worker, name=f'demo-worker-{i+1}', daemon=True).start()
    # Private event timeline used to choose honest cuts in post-production.
    def timeline():
        previous = None
        with (WORK / 'timeline.jsonl').open('a', encoding='utf-8') as log:
            while not app.STOP.wait(.5):
                with app.connect() as db:
                    state = app.processing_status(db)
                    statuses = list(map(tuple, db.execute('SELECT id,status,updated FROM reels ORDER BY saved_position')))
                signature = json.dumps(statuses)
                if signature != previous:
                    log.write(json.dumps({'time': time.time(), 'metrics': state['metrics'], 'statuses': statuses}) + '\n'); log.flush(); previous = signature
    threading.Thread(target=timeline, daemon=True).start()
    print(f'Demo ready, paused: http://127.0.0.1:{port} · {manifest["scope"]}', flush=True)
    try:
        server.serve_forever()
    finally:
        app.STOP.set(); server.server_close()


def report():
    manifest = read_json(WORK / 'manifest.json')
    app.DATA = WORK / 'library'
    with app.connect() as db:
        state = app.processing_status(db)
        outcomes = dict(db.execute('SELECT status,count(*) FROM reels GROUP BY status'))
        cache_count = db.execute('SELECT count(*) FROM inference_cache').fetchone()[0]
    source = Path(manifest['source'])
    original = sqlite3.connect((source / 'library.sqlite').as_uri() + '?mode=ro', uri=True)
    unchanged = fingerprint(original) == manifest['source_fingerprint']; original.close()
    hardware = subprocess.run(['powershell.exe', '-NoProfile', '-Command', "[pscustomobject]@{cpu=(Get-CimInstance Win32_Processor).Name;gpu=@((Get-CimInstance Win32_VideoController).Name)} | ConvertTo-Json -Compress"], capture_output=True, text=True)
    resolved = app.model_client.request('/api/show', {'model':app.MODEL}).get('details', {})
    result = {'sample_size': 50, 'showcase_size': 20, 'topics': manifest['topics'],
              'scope': manifest['scope'], 'warmup_examples': 2, 'models': {'vision':app.MODEL,'decision':app.DECISION_MODEL,'embedding':app.EMBED_MODEL},
              'workers': app.QUEUE_WINDOW, 'hardware': json.loads(hardware.stdout),
              'resolved_vision_model': {key:resolved.get(key) for key in ('family','parameter_size','quantization_level')},
              'model_disclosure': 'Configured model IDs are aliases. Interpret speed using the resolved model metadata, not the alias name.',
              'content_policy': manifest['content_policy'],
              'metrics': state['metrics'], 'outcomes': outcomes, 'source_unchanged': unchanged,
              'cache_entries_created_during_run': cache_count, 'accuracy_claim': 'Not evaluated; completion is not classification accuracy.'}
    write_json(WORK / 'benchmark.json', result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'serve', 'report'))
    parser.add_argument('--source', type=Path, default=ROOT / 'app' / 'data')
    parser.add_argument('--port', type=int, default=8770)
    parser.add_argument('--skip-warmup', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args.source)
    elif args.command == 'serve': serve(args.port, args.skip_warmup)
    else: report()
