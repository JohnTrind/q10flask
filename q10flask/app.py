import sys
import os

# Vendored deps first
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'vendor'))

from flask import Flask, render_template, request, jsonify
import json
import datetime
import subprocess
import platform

app = Flask(__name__)

NOTES_FILE = os.path.join(os.path.dirname(__file__), 'notes.json')

def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'r') as f:
            return json.load(f)
    return []

def save_notes(notes):
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f, indent=2)

def get_sysinfo():
    info = {}
    info['platform'] = platform.system()
    info['machine'] = platform.machine()
    info['node'] = platform.node()
    info['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Try to get uptime (works on QNX/Linux)
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.read().split()[0])
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            info['uptime'] = f"{h}h {m}m"
    except:
        info['uptime'] = 'n/a'

    # Try free memory
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            mem = {}
            for line in lines[:3]:
                k, v = line.split(':')
                mem[k.strip()] = v.strip()
            total = int(mem.get('MemTotal', '0 kB').split()[0])
            free = int(mem.get('MemFree', '0 kB').split()[0])
            info['mem_total'] = f"{total // 1024} MB"
            info['mem_free'] = f"{free // 1024} MB"
            info['mem_used'] = f"{(total - free) // 1024} MB"
    except:
        info['mem_total'] = 'n/a'
        info['mem_free'] = 'n/a'
        info['mem_used'] = 'n/a'

    return info

@app.route('/')
def index():
    return render_template('index.html', sysinfo=get_sysinfo())

@app.route('/api/sysinfo')
def api_sysinfo():
    return jsonify(get_sysinfo())

@app.route('/api/notes', methods=['GET'])
def get_notes():
    return jsonify(load_notes())

@app.route('/api/notes', methods=['POST'])
def add_note():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty'}), 400
    notes = load_notes()
    note = {
        'id': len(notes) + 1,
        'text': text,
        'ts': datetime.datetime.now().strftime('%H:%M %d/%m')
    }
    notes.append(note)
    save_notes(notes)
    return jsonify(note)

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    notes = load_notes()
    notes = [n for n in notes if n['id'] != note_id]
    save_notes(notes)
    return jsonify({'ok': True})

@app.route('/api/shell', methods=['POST'])
def run_shell():
    """Run a whitelisted shell command and return output."""
    ALLOWED = ['ls', 'pwd', 'whoami', 'date', 'uname', 'df', 'uptime', 'ps']
    data = request.get_json()
    cmd = data.get('cmd', '').strip()
    base = cmd.split()[0] if cmd else ''
    if base not in ALLOWED:
        return jsonify({'output': f"'{base}' not in whitelist: {', '.join(ALLOWED)}"})
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        output = result.stdout or result.stderr or '(no output)'
    except Exception as e:
        output = str(e)
    return jsonify({'output': output})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[q10flask] starting on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
