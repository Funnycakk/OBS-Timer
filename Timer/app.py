"""
OBS Timer Server — Production countdown timer for OBS Studio.

Provides:
  • Real-time WebSocket (Socket.IO) API for multi-client sync
  • HTTP REST API for Bitfocus Companion / Stream Deck control
  • HTML5 Canvas circular timer visualization

Run:
    python app.py

Then open http://localhost:5000 in a browser or OBS Browser Source.
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
import threading
import time
import os
import sys
import math

# ---------------------------------------------------------------------------
# Flask application setup
# ---------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(script_dir, "templates"),
    static_folder=os.path.join(script_dir, "static"),
)
app.config["SECRET_KEY"] = "obs-timer-secret-key"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------------------------------------------------------------------------
# Maximum allowed time: 99 minutes 59 seconds = 5999 seconds
# ---------------------------------------------------------------------------
MAX_SECONDS = 99 * 60 + 59  # 5999


# ===========================================================================
#  Timer Engine  — thread-safe server-side countdown
# ===========================================================================
class TimerEngine:
    """
    Manages countdown state with atomic operations.

    State machine:
        PAUSED  ──start──▶  RUNNING  ──(reaches 0)──▶  FINISHED
        RUNNING ──stop───▶  PAUSED
        *       ──reset──▶  PAUSED (00:00)
        *       ──setTime─▶ PAUSED (new time)

    The timer thread wakes every 0.1 s and decrements once per second using
    wall-clock deltas so it never drifts over long periods.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()

        # Persistent state
        self._status: str = "PAUSED"          # RUNNING | PAUSED | FINISHED
        self._remaining: float = 0.0          # seconds remaining (float for sub-second precision)
        self._initial: float = 0.0            # the value set by setTime (used for progress %)
        self._last_tick: float | None = None  # monotonic timestamp of last tick

        # Background thread
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ----- public commands ---------------------------------------------------

    def start(self) -> dict:
        """Begin / resume countdown."""
        with self.lock:
            if self._remaining <= 0:
                return self._state_dict()
            self._status = "RUNNING"
            self._last_tick = time.monotonic()
            self._ensure_thread()
            return self._broadcast()

    def stop(self) -> dict:
        """Pause the countdown."""
        with self.lock:
            if self._status == "RUNNING":
                self._apply_elapsed()
                self._status = "PAUSED"
            return self._broadcast()

    def reset(self) -> dict:
        """Set timer to 00:00 and stop."""
        with self.lock:
            self._status = "PAUSED"
            self._remaining = 0.0
            self._initial = 0.0
            self._last_tick = None
            return self._broadcast()

    def set_time(self, minutes: int = 0, seconds: int = 0) -> dict:
        """Set a new countdown value. Stops timer if running."""
        total = int(minutes) * 60 + int(seconds)
        total = max(0, min(total, MAX_SECONDS))
        with self.lock:
            self._status = "PAUSED"
            self._remaining = float(total)
            self._initial = float(total)
            self._last_tick = None
            return self._broadcast()

    def add_time(self, seconds: int = 10) -> dict:
        """Add seconds (works while running or paused)."""
        with self.lock:
            if self._status == "RUNNING":
                self._apply_elapsed()
            self._remaining = min(self._remaining + int(seconds), MAX_SECONDS)
            # Expand initial if needed (keeps progress ring sensible)
            if self._remaining > self._initial:
                self._initial = self._remaining
            # If timer was FINISHED and we added time, move to PAUSED
            if self._status == "FINISHED" and self._remaining > 0:
                self._status = "PAUSED"
            return self._broadcast()

    def subtract_time(self, seconds: int = 10) -> dict:
        """Subtract seconds (minimum 0)."""
        with self.lock:
            if self._status == "RUNNING":
                self._apply_elapsed()
            self._remaining = max(0.0, self._remaining - int(seconds))
            if self._remaining <= 0:
                self._remaining = 0.0
                if self._status == "RUNNING":
                    self._status = "FINISHED"
            return self._broadcast()

    def get_status(self) -> dict:
        """Return current state without side effects."""
        with self.lock:
            if self._status == "RUNNING":
                self._apply_elapsed()
            return self._state_dict()

    # ----- internal helpers --------------------------------------------------

    def _apply_elapsed(self) -> None:
        """Subtract wall-clock elapsed time since last tick (no-drift)."""
        if self._last_tick is not None:
            now = time.monotonic()
            elapsed = now - self._last_tick
            self._remaining = max(0.0, self._remaining - elapsed)
            self._last_tick = now

    def _state_dict(self) -> dict:
        """Build the JSON-serialisable state dictionary."""
        remaining_int = math.ceil(self._remaining) if self._status == "RUNNING" else int(self._remaining)
        remaining_int = max(0, remaining_int)
        mins, secs = divmod(remaining_int, 60)
        progress = 0.0
        if self._initial > 0:
            progress = (self._remaining / self._initial) * 100.0
            progress = max(0.0, min(100.0, progress))
        return {
            "status": self._status,
            "remainingSeconds": remaining_int,
            "initialSeconds": int(self._initial),
            "display": f"{mins:02d}:{secs:02d}",
            "progress": round(progress, 2),
        }

    def _broadcast(self) -> dict:
        """Emit current state to every connected Socket.IO client."""
        data = self._state_dict()
        socketio.emit("timer_update", data)
        return data

    # ----- background thread -------------------------------------------------

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._tick_loop, daemon=True)
            self._thread.start()

    def _tick_loop(self) -> None:
        """
        Runs in background. Every ~100 ms it checks the timer and emits
        once per whole-second transition so all clients stay in sync.
        """
        last_emitted_second: int | None = None

        while not self._stop_event.is_set():
            with self.lock:
                if self._status != "RUNNING":
                    break

                self._apply_elapsed()

                remaining_int = math.ceil(self._remaining)
                remaining_int = max(0, remaining_int)

                # Emit on every new whole-second boundary
                if last_emitted_second is None or remaining_int != last_emitted_second:
                    last_emitted_second = remaining_int

                    if self._remaining <= 0:
                        self._remaining = 0.0
                        self._status = "FINISHED"
                        self._broadcast()
                        break
                    else:
                        self._broadcast()

            time.sleep(0.1)


# ---------------------------------------------------------------------------
# Global timer instance
# ---------------------------------------------------------------------------
timer = TimerEngine()


# ===========================================================================
#  Web routes
# ===========================================================================

@app.route("/")
def index():
    """Serve the main timer page."""
    return render_template("index.html")


@app.route("/settime")
def settime_form():
    """Legacy set-time form page."""
    return render_template("settime.html")


# ===========================================================================
#  HTTP REST API  — for Bitfocus Companion / Stream Deck
# ===========================================================================

def _ok(data: dict) -> tuple:
    """Wrap timer state in a success JSON response."""
    return jsonify({"success": True, **data}), 200


def _err(msg: str, code: int = 400) -> tuple:
    """Return an error JSON response."""
    return jsonify({"success": False, "error": msg}), code


# ---------- Timer control endpoints ----------------------------------------

@app.route("/api/timer/start", methods=["POST"])
def api_timer_start():
    return _ok(timer.start())


@app.route("/api/timer/stop", methods=["POST"])
def api_timer_stop():
    return _ok(timer.stop())


@app.route("/api/timer/reset", methods=["POST"])
def api_timer_reset():
    return _ok(timer.reset())


@app.route("/api/timer/add", methods=["POST"])
def api_timer_add():
    seconds = request.args.get("seconds", default=10, type=int)
    return _ok(timer.add_time(seconds))


@app.route("/api/timer/subtract", methods=["POST"])
def api_timer_subtract():
    seconds = request.args.get("seconds", default=10, type=int)
    return _ok(timer.subtract_time(seconds))


@app.route("/api/timer/set", methods=["POST"])
def api_timer_set():
    minutes = request.args.get("minutes", default=0, type=int)
    seconds = request.args.get("seconds", default=0, type=int)
    total = minutes * 60 + seconds
    if total < 0 or total > MAX_SECONDS:
        return _err(f"Time must be between 0 and {MAX_SECONDS} seconds (99:59)")
    return _ok(timer.set_time(minutes, seconds))


@app.route("/api/timer/status", methods=["GET"])
def api_timer_status():
    return _ok(timer.get_status())


# ---------- Legacy endpoints (backward compatible with existing setup) ------

@app.route("/api/start", methods=["POST"])
def api_start_legacy():
    return _ok(timer.start())


@app.route("/api/stop", methods=["POST"])
def api_stop_legacy():
    return _ok(timer.stop())


@app.route("/api/reset", methods=["POST"])
def api_reset_legacy():
    return _ok(timer.reset())


@app.route("/api/set", methods=["POST"])
def api_set_legacy():
    data = request.get_json(silent=True) or {}
    h = int(data.get("hours", 0))
    m = int(data.get("minutes", 0))
    s = int(data.get("seconds", 0))
    total_seconds = h * 3600 + m * 60 + s
    mins, secs = divmod(min(total_seconds, MAX_SECONDS), 60)
    return _ok(timer.set_time(mins, secs))


@app.route("/api/add", methods=["POST"])
def api_add_legacy():
    data = request.get_json(silent=True) or {}
    seconds = int(data.get("seconds", 60))
    return _ok(timer.add_time(seconds))


@app.route("/api/remove", methods=["POST"])
def api_remove_legacy():
    data = request.get_json(silent=True) or {}
    seconds = int(data.get("seconds", 60))
    return _ok(timer.subtract_time(seconds))


@app.route("/api/status", methods=["GET"])
def api_status_legacy():
    return _ok(timer.get_status())


@app.route("/api/popup", methods=["POST", "GET"])
def api_popup():
    """Launch the tkinter set-time popup (Windows only)."""
    import subprocess
    popup_script = os.path.join(script_dir, "set_timer_window.py")
    if not os.path.exists(popup_script):
        return _err("set_timer_window.py not found", 404)
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen([sys.executable, popup_script], creationflags=flags)
        return jsonify({"success": True, "status": "popup_opened"})
    except Exception as e:
        return _err(str(e), 500)


# ===========================================================================
#  WebSocket (Socket.IO) API
# ===========================================================================

@socketio.on("connect")
def ws_connect():
    """Send current state to newly connected client."""
    emit("timer_update", timer.get_status())


@socketio.on("command")
def ws_command(data):
    """
    Accept JSON commands over WebSocket.
    Format:  {"action": "start"|"stop"|"reset"|"addTime"|"subtractTime"|"setTime"|"getStatus", ...}
    """
    if not isinstance(data, dict):
        emit("error", {"message": "Invalid command format"})
        return

    action = data.get("action", "")
    result = None

    if action == "start":
        result = timer.start()
    elif action == "stop":
        result = timer.stop()
    elif action == "reset":
        result = timer.reset()
    elif action == "addTime":
        seconds = int(data.get("seconds", 10))
        result = timer.add_time(seconds)
    elif action == "subtractTime":
        seconds = int(data.get("seconds", 10))
        result = timer.subtract_time(seconds)
    elif action == "setTime":
        minutes = int(data.get("minutes", 0))
        seconds = int(data.get("seconds", 0))
        result = timer.set_time(minutes, seconds)
    elif action == "getStatus":
        result = timer.get_status()
        emit("timer_update", result)
        return
    else:
        emit("error", {"message": f"Unknown action: {action}"})
        return

    # Successful command — state is already broadcast by the engine
    emit("command_ok", {"action": action, **result})


# Legacy socket events (backward compatible with existing frontend)
@socketio.on("start")
def ws_start():
    timer.start()


@socketio.on("stop")
def ws_stop():
    timer.stop()


@socketio.on("reset")
def ws_reset():
    timer.reset()


# ===========================================================================
#  Entry point
# ===========================================================================
if __name__ == "__main__":
    print("=" * 58)
    print("  OBS Timer Server v3.0")
    print("=" * 58)
    print()
    print("  Timer UI:      http://localhost:5000/")
    print("  Transparent:   http://localhost:5000/?transparent=true")
    print("  OBS Source:     http://localhost:5000/?transparent=true")
    print()
    print("  REST API:")
    print("    POST /api/timer/start")
    print("    POST /api/timer/stop")
    print("    POST /api/timer/reset")
    print("    POST /api/timer/add?seconds=10")
    print("    POST /api/timer/subtract?seconds=10")
    print("    POST /api/timer/set?minutes=5&seconds=0")
    print("    GET  /api/timer/status")
    print()
    print("  WebSocket: connect to http://localhost:5000")
    print('    emit("command", {"action": "start"})')
    print("=" * 58)

    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
