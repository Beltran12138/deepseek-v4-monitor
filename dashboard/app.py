import json
import queue
import sys
import threading
from pathlib import Path

from flask import Flask, Response, render_template

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

app = Flask(__name__)

_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def broadcast(data: dict):
    """Push a JSON event to all connected SSE clients."""
    payload = f"data: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


@app.route("/")
def index():
    signals = db.get_recent_signals(50)
    markets = db.get_markets()
    return render_template("index.html", signals=signals, markets=markets)


@app.route("/stream")
def stream():
    q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        try:
            while True:
                try:
                    yield q.get(timeout=30)
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/signals")
def api_signals():
    rows = db.get_recent_signals(50)
    return [dict(r) for r in rows]


@app.route("/api/markets")
def api_markets():
    rows = db.get_markets()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
