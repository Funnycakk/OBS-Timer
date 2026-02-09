# OBS Timer with Stream Deck / Bitfocus Companion Integration

A production-ready countdown timer for **OBS Studio** with a circular canvas
progress ring, real-time WebSocket sync, and a full HTTP REST API designed for
**Bitfocus Companion** and **Stream Deck** control.

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.1-green)
![Socket.IO](https://img.shields.io/badge/Socket.IO-realtime-orange)

---

## Features

| Feature | Description |
|---------|-------------|
| ⏱ Countdown Timer | Accurate server-side countdown (no drift) |
| 🎨 Circular Progress Ring | HTML5 Canvas with color-coded status |
| 🟢🟡🔴 Status Colors | Green (running), Orange (≤ 10 s warning), Red (finished/paused) |
| 🔴 Finish Flash | Time display flashes red when timer reaches 00:00 |
| 🌐 Multi-Client Sync | All connected browsers update simultaneously via WebSocket |
| 🎮 Stream Deck Ready | HTTP REST API for Bitfocus Companion buttons |
| 📡 WebSocket API | Socket.IO commands for advanced integrations |
| 🖥 OBS Browser Source | Transparent background mode (`?transparent=true`) |
| ⌨ Keyboard Shortcuts | Space (start/stop), R (reset), ↑↓ (±10 s) |
| 🕐 Time Presets | 1, 2, 5, 10, 15 minute quick-set buttons |
| 🔄 Auto-Reconnect | WebSocket reconnects automatically on disconnect |
| 📐 Responsive | Works at 400×400 and 800×200 (lower-third) |

---

## Installation

### 1. Install Python dependencies

```bash
cd Timer
pip install -r requirements.txt
```

### 2. Start the server

```bash
python app.py
```

The server starts on **http://localhost:5000**.

> **Windows shortcuts:**
> - Double-click `start_timer.bat` to launch with a console window
> - Run `start_timer_silent.vbs` to launch silently in the background

---

## OBS Browser Source Setup

1. In OBS, add a **Browser Source** to your scene.
2. Configure:

| Setting | Value |
|---------|-------|
| **URL** | `http://localhost:5000/?transparent=true` |
| **Width** | `400` |
| **Height** | `400` |
| **Custom CSS** | *(leave empty)* |

3. ✅ Check **"Shutdown source when not visible"**
4. ✅ Check **"Refresh browser when scene becomes active"**

> The `?transparent=true` parameter hides controls and makes the background
> transparent so only the timer ring + digits are visible.

### Wide / Lower-Third Layout

For a horizontal bar layout, set the browser source to **800 × 200** — the CSS
will adapt automatically.

---

## Controlling the Timer

### Option A — Web UI

Open **http://localhost:5000** in any browser. You get six buttons, preset
buttons, and keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Space` | Start / Stop (toggle) |
| `R` | Reset to 00:00 |
| `↑` | Add 10 seconds |
| `↓` | Subtract 10 seconds |

### Option B — Bitfocus Companion (Stream Deck)

Add **Generic HTTP** actions for each button. All requests are `POST` unless
noted.

#### Start Timer
```
POST http://localhost:5000/api/timer/start
```

#### Stop / Pause Timer
```
POST http://localhost:5000/api/timer/stop
```

#### Reset Timer
```
POST http://localhost:5000/api/timer/reset
```

#### Add 10 Seconds
```
POST http://localhost:5000/api/timer/add?seconds=10
```

#### Subtract 10 Seconds
```
POST http://localhost:5000/api/timer/subtract?seconds=10
```

#### Set Timer to 5 Minutes
```
POST http://localhost:5000/api/timer/set?minutes=5&seconds=0
```

#### Set Timer to 10 Minutes 30 Seconds
```
POST http://localhost:5000/api/timer/set?minutes=10&seconds=30
```

#### Get Current Status
```
GET http://localhost:5000/api/timer/status
```

**Response format (all endpoints):**
```json
{
  "success": true,
  "status": "RUNNING",
  "remainingSeconds": 125,
  "initialSeconds": 300,
  "display": "02:05",
  "progress": 41.67
}
```

#### Suggested Stream Deck Layout

```
┌─────────┬─────────┬─────────┬─────────┐
│  1 min  │  5 min  │ 10 min  │ 15 min  │
├─────────┼─────────┼─────────┼─────────┤
│  START  │  STOP   │  RESET  │ +1 min  │
└─────────┴─────────┴─────────┴─────────┘
```

### Option C — WebSocket (Socket.IO)

Connect to `http://localhost:5000` with a Socket.IO client and emit `command`
events:

```javascript
const socket = io("http://localhost:5000");

// Send commands
socket.emit("command", { action: "start" });
socket.emit("command", { action: "stop" });
socket.emit("command", { action: "reset" });
socket.emit("command", { action: "addTime",      seconds: 10 });
socket.emit("command", { action: "subtractTime",  seconds: 10 });
socket.emit("command", { action: "setTime",       minutes: 5, seconds: 30 });
socket.emit("command", { action: "getStatus" });

// Receive updates
socket.on("timer_update", (data) => {
    console.log(data);
    // { status, remainingSeconds, initialSeconds, display, progress }
});
```

---

## HTTP REST API Reference

All endpoints return JSON with `{ "success": true/false, ... }`.

### Primary Endpoints

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `POST` | `/api/timer/start` | — | Start / resume countdown |
| `POST` | `/api/timer/stop` | — | Pause countdown |
| `POST` | `/api/timer/reset` | — | Reset to 00:00 |
| `POST` | `/api/timer/add` | `?seconds=N` | Add N seconds |
| `POST` | `/api/timer/subtract` | `?seconds=N` | Subtract N seconds |
| `POST` | `/api/timer/set` | `?minutes=M&seconds=S` | Set countdown value |
| `GET`  | `/api/timer/status` | — | Get current state |

### Legacy Endpoints (backward compatible)

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/start` | — | Start |
| `POST` | `/api/stop` | — | Stop |
| `POST` | `/api/reset` | — | Reset |
| `POST` | `/api/set` | `{"minutes":5}` or `{"seconds":300}` | Set time |
| `POST` | `/api/add` | `{"seconds":60}` | Add time |
| `POST` | `/api/remove` | `{"seconds":60}` | Remove time |
| `GET`  | `/api/status` | — | Status |

---

## WebSocket (Socket.IO) API

### Events emitted by client → server

| Event | Payload | Description |
|-------|---------|-------------|
| `command` | `{"action": "start"}` | Start timer |
| `command` | `{"action": "stop"}` | Stop timer |
| `command` | `{"action": "reset"}` | Reset timer |
| `command` | `{"action": "addTime", "seconds": 10}` | Add time |
| `command` | `{"action": "subtractTime", "seconds": 10}` | Subtract time |
| `command` | `{"action": "setTime", "minutes": 5, "seconds": 30}` | Set time |
| `command` | `{"action": "getStatus"}` | Request status |

### Events emitted by server → client

| Event | Payload | Description |
|-------|---------|-------------|
| `timer_update` | `{status, remainingSeconds, initialSeconds, display, progress}` | State broadcast (every second while running, and on any change) |
| `error` | `{"message": "..."}` | Error response |
| `command_ok` | `{action, status, remainingSeconds, ...}` | Acknowledgement |

---

## Visual Indicators

| Condition | Ring Color | Text Color |
|-----------|-----------|------------|
| Running (> 10 s) | 🟢 Green | White |
| Running (≤ 10 s) | 🟡 Orange | Orange |
| Paused | ⚪ White | Red label |
| Finished (00:00) | 🔴 Red | Red (flashing) |

---

## File Structure

```
Timer/
├── app.py                  # Flask server + Socket.IO + timer engine
├── requirements.txt        # Python dependencies
├── start_timer.bat         # Windows launcher (console)
├── start_timer_silent.vbs  # Windows launcher (silent)
├── set_timer_popup.bat     # Legacy popup launcher
├── set_timer_window.py     # Tkinter popup (legacy)
├── obs_timer_script.py     # OBS Scripts integration
├── timer.py                # Legacy server (kept for compatibility)
├── static/
│   ├── style.css           # Timer styling & responsive layout
│   └── timer.js            # Socket.IO client & canvas rendering
├── templates/
│   ├── index.html          # Main timer page (new)
│   ├── timer.html          # Legacy timer page
│   └── settime.html        # Set-time form page
└── certs/                  # SSL certificates (optional)
```

---

## Customisation

### Change Default Port

Edit the last line of `app.py`:

```python
socketio.run(app, host="0.0.0.0", port=8080, debug=False, allow_unsafe_werkzeug=True)
```

### Network Access

The server binds to `0.0.0.0`, so any device on your LAN can reach it at
`http://<your-ip>:5000/`.

### Change Colors

Edit CSS custom properties at the top of `static/style.css`:

```css
:root {
    --color-running:  #4caf50;
    --color-warning:  #ff9800;
    --color-finished: #f44336;
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Timer not visible in OBS** | Make sure `app.py` is running. Refresh the Browser Source. |
| **Companion buttons not working** | Verify the server is on port 5000. Check firewall. |
| **WebSocket disconnects** | The client auto-reconnects. Check network stability. |
| **Timer drifts over time** | Timer uses `time.monotonic()` wall-clock deltas — no drift. |
| **Port 5000 already in use** | Change the port in `app.py` (see above). |
| **Old `timer.py` still running** | Kill it first — only one server can use port 5000. |
| **Controls visible in OBS** | Add `?transparent=true` to the URL. |

---

## License

Free to use and modify for your streaming needs!
