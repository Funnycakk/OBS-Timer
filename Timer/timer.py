from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
import threading
import time
import sys
import os
from datetime import timedelta

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(script_dir, 'templates'),
            static_folder=os.path.join(script_dir, 'static'))
app.config['SECRET_KEY'] = 'timer-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

class Timer:
    def __init__(self):
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.initial_seconds = 0
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def set_time(self, seconds):
        with self.lock:
            self.total_seconds = seconds
            self.remaining_seconds = seconds
            self.initial_seconds = seconds
            self.broadcast_update()
    
    def add_time(self, seconds):
        with self.lock:
            self.total_seconds += seconds
            self.remaining_seconds += seconds
            self.initial_seconds = max(self.initial_seconds, self.total_seconds)
            self.broadcast_update()
    
    def remove_time(self, seconds):
        with self.lock:
            self.total_seconds = max(0, self.total_seconds - seconds)
            self.remaining_seconds = max(0, self.remaining_seconds - seconds)
            self.broadcast_update()
    
    def start(self):
        with self.lock:
            if not self.running and self.total_seconds > 0:
                self.running = True
                if self.thread is None or not self.thread.is_alive():
                    self.thread = threading.Thread(target=self._run_timer)
                    self.thread.daemon = True
                    self.thread.start()
    
    def stop(self):
        with self.lock:
            self.running = False
            self.broadcast_update()
    
    def reset(self):
        with self.lock:
            self.running = False
            self.remaining_seconds = self.initial_seconds
            self.total_seconds = self.initial_seconds
            self.broadcast_update()
    
    def _run_timer(self):
        while True:
            with self.lock:
                if not self.running:
                    break
                
                if self.remaining_seconds > 0:
                    self.remaining_seconds -= 1
                    self.total_seconds -= 1
                else:
                    self.running = False
                
                self.broadcast_update()
            
            time.sleep(1)
    
    def broadcast_update(self):
        data = self.get_status()
        socketio.emit('timer_update', data)
    
    def get_status(self):
        hours = self.remaining_seconds // 3600
        minutes = (self.remaining_seconds % 3600) // 60
        seconds = self.remaining_seconds % 60
        
        progress = 0
        if self.initial_seconds > 0:
            progress = (self.remaining_seconds / self.initial_seconds) * 100
        
        return {
            'remaining_seconds': self.remaining_seconds,
            'total_seconds': self.total_seconds,
            'initial_seconds': self.initial_seconds,
            'running': self.running,
            'time_display': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            'progress': progress
        }

# Global timer instance
timer = Timer()

# Web Routes
@app.route('/')
def index():
    return render_template('timer.html')

@app.route('/settime')
def settime_form():
    return render_template('settime.html')

# Serve static files (CSS, JS, images, etc.)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/background/<path:filename>')
def serve_background(filename):
    background_dir = os.path.join(script_dir, 'background')
    return send_from_directory(background_dir, filename)

@app.route('/api/status')
def status():
    return jsonify(timer.get_status())

# API Endpoints for Companion Control
@app.route('/api/start', methods=['POST'])
def api_start():
    timer.start()
    return jsonify({'status': 'started', 'timer': timer.get_status()})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    timer.stop()
    return jsonify({'status': 'stopped', 'timer': timer.get_status()})

@app.route('/api/reset', methods=['POST'])
def api_reset():
    timer.reset()
    return jsonify({'status': 'reset', 'timer': timer.get_status()})

@app.route('/api/set', methods=['POST'])
def api_set():
    data = request.get_json() or {}
    seconds = data.get('seconds', 0)
    
    # Also accept minutes parameter
    if 'minutes' in data:
        seconds = data['minutes'] * 60
    
    # Or accept hours, minutes, seconds
    if 'hours' in data or 'minutes' in data or 'seconds' in data:
        h = data.get('hours', 0)
        m = data.get('minutes', 0)
        s = data.get('seconds', 0)
        seconds = h * 3600 + m * 60 + s
    
    timer.set_time(int(seconds))
    return jsonify({'status': 'time_set', 'timer': timer.get_status()})

@app.route('/api/add', methods=['POST'])
def api_add():
    data = request.get_json() or {}
    seconds = data.get('seconds', 60)  # Default: add 1 minute
    timer.add_time(int(seconds))
    return jsonify({'status': 'time_added', 'timer': timer.get_status()})

@app.route('/api/remove', methods=['POST'])
def api_remove():
    data = request.get_json() or {}
    seconds = data.get('seconds', 60)  # Default: remove 1 minute
    timer.remove_time(int(seconds))
    return jsonify({'status': 'time_removed', 'timer': timer.get_status()})

@app.route('/api/popup', methods=['POST', 'GET'])
def api_popup():
    """Trigger the set time popup window"""
    import subprocess
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    popup_script = os.path.join(script_dir, 'set_timer_window.py')
    
    # Launch the popup without console window (tkinter window will still show)
    if os.name == 'nt':  # Windows
        subprocess.Popen([sys.executable, popup_script],
                        creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen([sys.executable, popup_script])
    
    return jsonify({'status': 'popup_opened'})

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    emit('timer_update', timer.get_status())

@socketio.on('start')
def handle_start():
    timer.start()

@socketio.on('stop')
def handle_stop():
    timer.stop()

@socketio.on('reset')
def handle_reset():
    timer.reset()

if __name__ == '__main__':
    # Set initial time to 2 minutes and 1 second (UPDATED VERSION)
    timer.set_time(121)
    
    print("=" * 50)
    print("OBS Timer Server Starting... [v2.01]")
    print("=" * 50)
    print("OBS Browser Source URL: http://localhost:5000/")
    print("API Endpoint: http://localhost:5000/api/")
    print("")
    print("Companion API Commands:")
    print("  Start:  POST http://localhost:5000/api/start")
    print("  Stop:   POST http://localhost:5000/api/stop")
    print("  Reset:  POST http://localhost:5000/api/reset")
    print("  Set:    POST http://localhost:5000/api/set")
    print("          Body: {\"seconds\": 300} or {\"minutes\": 5}")
    print("  Add:    POST http://localhost:5000/api/add")
    print("          Body: {\"seconds\": 60}")
    print("  Remove: POST http://localhost:5000/api/remove")
    print("          Body: {\"seconds\": 60}")
    print("=" * 50)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
