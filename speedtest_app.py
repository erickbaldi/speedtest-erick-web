import os
import sqlite3
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
import speedtest

app = Flask(__name__)

# Configura ProxyFix per lavorare correttamente dietro NGINX reverse proxy HTTPS
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'speedtest_history.db')

# Inserisci eventuali ID numerici di server preferiti (es. [12345, 67890])
PREFERRED_SERVERS = []

# Cache risultati (300 secondi = 5 minuti) e lock per evitare test simultanei
CACHE_TTL_SECONDS = 300
_test_lock = threading.Lock()
_cached_result = None
_cached_timestamp = 0.0
_cached_servers = None
_cached_servers_ts = 0.0


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                download REAL NOT NULL,
                upload REAL NOT NULL,
                ping REAL NOT NULL,
                server TEXT NOT NULL
            )
        ''')
        conn.commit()


def save_history(entry):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO history (timestamp, download, upload, ping, server) VALUES (?, ?, ?, ?, ?)',
            (entry['timestamp'], entry['download'], entry['upload'], entry['ping'], entry['server'])
        )
        conn.commit()


def get_recent_history(limit=15):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT timestamp, download, upload, ping, server FROM history ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/history')
def api_history():
    try:
        items = get_recent_history(15)
        now = time.time()
        valid_cache = None
        if _cached_result and (now - _cached_timestamp) < CACHE_TTL_SECONDS:
            valid_cache = dict(_cached_result)
            valid_cache['cached'] = True
            valid_cache['cache_age'] = int(now - _cached_timestamp)
        return jsonify({
            'status': 'success',
            'history': items,
            'latest_cached': valid_cache
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/servers')
def api_servers():
    global _cached_servers, _cached_servers_ts
    now = time.time()
    if _cached_servers is not None and (now - _cached_servers_ts) < 1800:
        return jsonify({'status': 'success', 'servers': _cached_servers})

    try:
        st = speedtest.Speedtest(secure=True)
        raw_servers = st.get_servers(PREFERRED_SERVERS if PREFERRED_SERVERS else None)
        flat = []
        for dist, srv_list in raw_servers.items():
            for srv in srv_list:
                flat.append({
                    'id': int(srv['id']),
                    'label': f"{srv['sponsor']} - {srv['name']} ({round(float(dist), 1)} km)",
                    'distance': float(dist)
                })
        flat.sort(key=lambda x: x['distance'])
        _cached_servers = flat[:20]
        _cached_servers_ts = now
        return jsonify({'status': 'success', 'servers': _cached_servers})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'servers': []}), 500


@app.route('/api/speedtest', methods=['POST', 'GET'])
def run_speedtest():
    global _cached_result, _cached_timestamp

    force_refresh = request.args.get('force', '0') == '1'
    selected_server_id = request.args.get('server_id', '').strip()

    now = time.time()
    if (
        not force_refresh
        and not selected_server_id
        and _cached_result is not None
        and (now - _cached_timestamp) < CACHE_TTL_SECONDS
    ):
        resp = dict(_cached_result)
        resp['cached'] = True
        resp['cache_age'] = int(now - _cached_timestamp)
        return jsonify(resp)

    if not _test_lock.acquire(blocking=False):
        return jsonify({
            'status': 'busy',
            'message': 'Un altro speed test è già in esecuzione. Riprova tra pochi secondi.'
        }), 429

    try:
        st = speedtest.Speedtest(secure=True)

        if selected_server_id.isdigit():
            st.get_servers([int(selected_server_id)])
            st.get_best_server()
        elif PREFERRED_SERVERS:
            try:
                st.get_servers(PREFERRED_SERVERS)
                st.get_best_server()
            except Exception:
                st.get_servers()
                st.get_best_server()
        else:
            st.get_best_server()

        download_speed = round(st.download() / 1_000_000, 2)
        upload_speed = round(st.upload() / 1_000_000, 2)
        ping = round(st.results.ping, 1)
        server_name = f"{st.results.server['sponsor']} ({st.results.server['name']})"
        timestamp_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        result = {
            'status': 'success',
            'download': download_speed,
            'upload': upload_speed,
            'ping': ping,
            'server': server_name,
            'timestamp': timestamp_str,
            'cached': False
        }

        save_history(result)
        _cached_result = result
        _cached_timestamp = time.time()

        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        _test_lock.release()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7878, debug=False)
