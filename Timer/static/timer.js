/* ==========================================================================
   OBS Timer — Client-side logic
   Handles Socket.IO connection, canvas rendering, and keyboard shortcuts.
   ========================================================================== */

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const canvas          = document.getElementById("timerCanvas");
const ctx             = canvas.getContext("2d");
const timeDisplay     = document.getElementById("timeDisplay");
const statusIndicator = document.getElementById("statusIndicator");
const controls        = document.getElementById("controls");
const keyboardHint    = document.getElementById("keyboardHint");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentState = {
    status:           "PAUSED",
    remainingSeconds: 0,
    initialSeconds:   0,
    display:          "00:00",
    progress:         0,
};

// ---------------------------------------------------------------------------
// Transparent / OBS mode
// ---------------------------------------------------------------------------
const params = new URLSearchParams(window.location.search);
if (params.get("transparent") === "true" || params.get("obs") === "true") {
    document.body.classList.add("transparent");
}

// ---------------------------------------------------------------------------
// Socket.IO connection with auto-reconnect
// ---------------------------------------------------------------------------
const socket = io({
    reconnection:         true,
    reconnectionAttempts: Infinity,
    reconnectionDelay:    500,
    reconnectionDelayMax: 5000,
});

socket.on("connect", () => {
    console.log("[Timer] Connected to server");
});

socket.on("disconnect", (reason) => {
    console.warn("[Timer] Disconnected:", reason);
});

socket.on("reconnect", (attempt) => {
    console.log("[Timer] Reconnected after", attempt, "attempts");
});

// ---------------------------------------------------------------------------
// Receive timer updates from server
// ---------------------------------------------------------------------------
socket.on("timer_update", (data) => {
    currentState = data;
    applyState();
});

socket.on("error", (data) => {
    console.error("[Timer] Server error:", data.message);
});

// ---------------------------------------------------------------------------
// Apply state to DOM + trigger canvas redraw
// ---------------------------------------------------------------------------
function applyState() {
    const s = currentState;

    // Time display text
    timeDisplay.textContent = s.display;

    // Status label + CSS class
    const statusLower = s.status.toLowerCase();       // running | paused | finished
    statusIndicator.textContent = s.status;
    statusIndicator.className   = "status-indicator";

    // Finished → flash effect
    timeDisplay.classList.remove("flash", "warning");

    if (s.status === "FINISHED") {
        statusIndicator.classList.add("finished");
        timeDisplay.classList.add("flash");
    } else if (s.status === "RUNNING" && s.remainingSeconds <= 10 && s.remainingSeconds > 0) {
        // Warning threshold: ≤10 s remaining
        statusIndicator.classList.add("warning");
        timeDisplay.classList.add("warning");
    } else if (s.status === "RUNNING") {
        statusIndicator.classList.add("running");
    } else {
        statusIndicator.classList.add("paused");
    }

    drawCanvas();
}

// ---------------------------------------------------------------------------
// Canvas rendering — circular progress ring
// ---------------------------------------------------------------------------
const RING_LINE_WIDTH = 20;

function drawCanvas() {
    const w  = canvas.width;
    const h  = canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(cx, cy) - RING_LINE_WIDTH / 2 - 10; // 10px padding

    // Clear
    ctx.clearRect(0, 0, w, h);

    // ----- Background track (dim ring) ------------------------------------
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
    ctx.lineWidth   = RING_LINE_WIDTH;
    ctx.stroke();

    // ----- Progress arc ---------------------------------------------------
    const progress = currentState.progress / 100;   // 0..1
    if (progress > 0) {
        const startAngle = -Math.PI / 2;                          // 12-o'clock
        const endAngle   = startAngle + Math.PI * 2 * progress;

        // Choose ring color based on state
        let ringColor = "#ffffff";
        if (currentState.status === "FINISHED") {
            ringColor = "#f44336";
        } else if (currentState.status === "RUNNING" && currentState.remainingSeconds <= 10) {
            ringColor = "#ff9800";
        } else if (currentState.status === "RUNNING") {
            ringColor = "#4caf50";
        }

        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, endAngle);
        ctx.strokeStyle = ringColor;
        ctx.lineWidth   = RING_LINE_WIDTH;
        ctx.lineCap     = "round";
        ctx.stroke();
    }

    // ----- Inner subtle ring highlight ------------------------------------
    ctx.beginPath();
    ctx.arc(cx, cy, radius - RING_LINE_WIDTH / 2, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth   = 1;
    ctx.stroke();
}

// ---------------------------------------------------------------------------
// Smooth rendering loop (~10 fps fallback to keep canvas crisp)
// ---------------------------------------------------------------------------
let rafId = null;
function renderLoop() {
    drawCanvas();
    rafId = requestAnimationFrame(renderLoop);
}
// We rely on server pushes for state; just keep the canvas painted.
renderLoop();

// ---------------------------------------------------------------------------
// Commands → server
// ---------------------------------------------------------------------------

/**
 * Send a command via Socket.IO.
 * @param {string} action  One of: start, stop, reset, addTime, subtractTime, setTime, getStatus
 * @param {object} [extra] Additional payload fields, e.g. {seconds: 10}
 */
function timerCmd(action, extra) {
    socket.emit("command", { action, ...extra });
}

/**
 * Prompt the user for MM:SS and send setTime command.
 */
function promptSetTime() {
    const input = prompt("Enter time (MM:SS):", "02:00");
    if (!input) return;

    const parts = input.trim().split(":");
    if (parts.length === 2) {
        const m = parseInt(parts[0], 10) || 0;
        const s = parseInt(parts[1], 10) || 0;
        if (m < 0 || s < 0 || s >= 60 || m > 99) {
            alert("Invalid time. Use MM:SS (max 99:59).");
            return;
        }
        timerCmd("setTime", { minutes: m, seconds: s });
    } else {
        alert("Invalid format. Please use MM:SS (e.g., 05:30).");
    }
}

/**
 * Set a preset time.
 */
function setPreset(minutes, seconds) {
    timerCmd("setTime", { minutes, seconds });
}

// ---------------------------------------------------------------------------
// Keyboard shortcuts
// ---------------------------------------------------------------------------
document.addEventListener("keydown", (e) => {
    // Ignore if user is in an input / prompt
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    switch (e.code) {
        case "Space":
            e.preventDefault();
            if (currentState.status === "RUNNING") {
                timerCmd("stop");
            } else {
                timerCmd("start");
            }
            break;
        case "KeyR":
            timerCmd("reset");
            break;
        case "ArrowUp":
            e.preventDefault();
            timerCmd("addTime", { seconds: 10 });
            break;
        case "ArrowDown":
            e.preventDefault();
            timerCmd("subtractTime", { seconds: 10 });
            break;
    }
});

// ---------------------------------------------------------------------------
// Initial draw
// ---------------------------------------------------------------------------
drawCanvas();
