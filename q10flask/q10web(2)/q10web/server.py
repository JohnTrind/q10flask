#!/usr/bin/env python
"""
q10ide - Zero-dependency Python IDE for BlackBerry Q10 / BB10
Pure Python stdlib only. Compatible with Python 3.2+
CodeMirror loaded from CDN for syntax highlighting.

Run:   python server.py
Open:  http://<Q10-IP>:5000
Stop:  Ctrl+C  (on Q10: metamode -> c -> c)
"""
import sys
import os
import json
import datetime
import platform
import subprocess
import traceback
import shutil

if sys.version_info[0] < 3:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
    from urlparse import urlparse, parse_qs
    from urllib import unquote
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs, unquote

# ------------------------------------------------------------------ config ---
PORT           = int(os.environ.get('PORT', 5000))
ROOT           = os.path.expanduser('~')
SHELL_ALLOW    = ['ls','pwd','whoami','date','uname','df','uptime',
                  'ps','ifconfig','cat','head','tail','mkdir','touch','mv']
MAX_EDIT_BYTES = 256 * 1024

# ----------------------------------------------------------------- helpers ---
def safe_path(rel):
    rel  = unquote(rel or '').lstrip('/')
    full = os.path.normpath(os.path.join(ROOT, rel))
    if not full.startswith(ROOT):
        return None
    return full

def sysinfo():
    d = {
        'platform': platform.system(),
        'machine':  platform.machine(),
        'node':     platform.node(),
        'python':   sys.version.split()[0],
        'time':     datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    try:
        with open('/proc/uptime') as f:
            s = float(f.read().split()[0])
            d['uptime'] = '{}h {}m'.format(int(s//3600), int((s%3600)//60))
    except Exception:
        d['uptime'] = 'n/a'
    try:
        with open('/proc/meminfo') as f:
            mem = {}
            for line in f.readlines()[:3]:
                k, v = line.split(':')
                mem[k.strip()] = v.strip()
            total = int(mem.get('MemTotal','0 kB').split()[0])
            free  = int(mem.get('MemFree', '0 kB').split()[0])
            d['mem_total'] = '{} MB'.format(total // 1024)
            d['mem_free']  = '{} MB'.format(free  // 1024)
            d['mem_used']  = '{} MB'.format((total - free) // 1024)
    except Exception:
        d['mem_total'] = d['mem_free'] = d['mem_used'] = 'n/a'
    return d

def fmt_size(n):
    for u in ['B','KB','MB','GB']:
        if n < 1024: return '{} {}'.format(int(n), u)
        n /= 1024.0
    return '{} GB'.format(round(n, 1))

def tree(rel=''):
    full = safe_path(rel)
    if not full or not os.path.isdir(full):
        return []
    out = []
    try:
        names = sorted(os.listdir(full),
                       key=lambda n: (not os.path.isdir(os.path.join(full,n)), n.lower()))
    except OSError:
        return []
    for name in names:
        if name.startswith('.'):
            continue
        fp = os.path.join(full, name)
        r  = os.path.relpath(fp, ROOT)
        try:
            is_dir = os.path.isdir(fp)
            node = {
                'name': name,
                'rel':  r,
                'type': 'dir' if is_dir else 'file',
                'size': '' if is_dir else fmt_size(os.path.getsize(fp)),
            }
            if is_dir:
                node['children'] = tree(r)
            out.append(node)
        except OSError:
            pass
    return out

def read_file(rel):
    full = safe_path(rel)
    if not full or not os.path.isfile(full):
        return None, 'not found'
    sz = os.path.getsize(full)
    if sz > MAX_EDIT_BYTES:
        return None, 'file too large ({})'.format(fmt_size(sz))
    try:
        with open(full, 'r', errors='replace') as f:
            return f.read(), None
    except Exception as e:
        return None, str(e)

def write_file(rel, content):
    full = safe_path(rel)
    if not full: return 'invalid path'
    try:
        d = os.path.dirname(full)
        if d and not os.path.exists(d):
            os.makedirs(d)
        with open(full, 'w') as f:
            f.write(content)
        return None
    except Exception as e:
        return str(e)

def create_node(rel, kind):
    full = safe_path(rel)
    if not full: return 'invalid path'
    try:
        if kind == 'dir':
            os.makedirs(full)
        else:
            d = os.path.dirname(full)
            if d and not os.path.exists(d):
                os.makedirs(d)
            with open(full, 'w') as f:
                f.write('')
        return None
    except Exception as e:
        return str(e)

def rename_node(rel, new_name):
    full = safe_path(rel)
    if not full: return 'invalid path'
    new_full = os.path.join(os.path.dirname(full), new_name)
    if not new_full.startswith(ROOT): return 'invalid target'
    try:
        os.rename(full, new_full)
        return None
    except Exception as e:
        return str(e)

def delete_node(rel):
    full = safe_path(rel)
    if not full: return 'invalid path'
    try:
        if os.path.isdir(full): shutil.rmtree(full)
        else: os.remove(full)
        return None
    except Exception as e:
        return str(e)

def run_cmd(cmd):
    base = cmd.strip().split()[0] if cmd.strip() else ''
    if base not in SHELL_ALLOW:
        return "'{}' not allowed. Permitted: {}".format(base, ', '.join(SHELL_ALLOW))
    try:
        proc = subprocess.Popen(cmd, shell=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:    out, err = proc.communicate(timeout=5)
        except Exception:
            proc.kill(); out, err = proc.communicate()
        return (out or err or b'(no output)').decode('utf-8', errors='replace')
    except Exception as e:
        return str(e)

# =============================================================================
#  SPA  —  single HTML file, everything inline
# =============================================================================
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Q10:IDE</title>

<link  rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<link  rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/dracula.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/shell/shell.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/selection/active-line.min.js"></script>

<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&family=Inconsolata:wght@400;700&display=swap');
:root{
  --bg:#09090e; --bg2:#0e0e16; --bg3:#13131c; --bg4:#181824;
  --cyan:#00e5ff; --cyan2:#00b8cc; --cyan3:#002a33;
  --amber:#ffb300; --red:#ff3d57; --green:#69ff47;
  --text:#cce8ff; --dim:#334455; --dim2:#1e2d3d;
  --border:#00e5ff1a;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--bg);color:var(--text);
  font-family:'Inconsolata',monospace;font-size:13px;overflow:hidden}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:9000;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,
  rgba(0,0,0,.04) 3px,rgba(0,0,0,.04) 4px)}

/* ── main layout ── */
#ide{display:flex;flex-direction:column;height:100vh}

/* header */
header{display:flex;align-items:center;gap:8px;padding:5px 10px;
  border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0}
.logo{font-family:'VT323',monospace;font-size:21px;color:var(--cyan);
  text-shadow:0 0 14px var(--cyan);letter-spacing:3px}
.logo em{color:var(--amber);font-style:normal}
#file-title{flex:1;font-size:11px;color:var(--dim);overflow:hidden;
  white-space:nowrap;text-overflow:ellipsis}
#file-title.active{color:var(--cyan)}
#save-st{font-size:11px;white-space:nowrap}
#save-st.ok{color:var(--green)}
#save-st.err{color:var(--red)}
#clock{font-size:11px;color:var(--dim);white-space:nowrap}
.dot{width:7px;height:7px;border-radius:50%;background:var(--cyan);
  box-shadow:0 0 8px var(--cyan);animation:blink 2s infinite;flex-shrink:0}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}

/* toolbar */
#toolbar{display:flex;align-items:center;gap:3px;padding:4px 8px;
  border-bottom:1px solid var(--border);background:var(--bg2);flex-shrink:0;flex-wrap:wrap}
.sep{width:1px;height:16px;background:var(--border);margin:0 3px}

/* buttons */
button{background:var(--bg3);border:1px solid var(--dim2);color:var(--text);
  font-family:'Inconsolata',monospace;font-size:11px;padding:4px 9px;
  cursor:pointer;letter-spacing:.5px;text-transform:uppercase;transition:.1s;white-space:nowrap}
button:hover{border-color:var(--cyan2);color:var(--cyan)}
button:active{background:var(--cyan3)}
button.pri{border-color:var(--cyan2);color:var(--cyan)}
button.amb{border-color:var(--amber);color:var(--amber)}
button.dan{border-color:var(--red);color:var(--red)}
button.dan:active{background:#2a0010}
button.sm{padding:2px 6px;font-size:11px}

/* body = tree + editor */
#body{display:flex;flex:1;overflow:hidden}

/* tree */
#tree-panel{width:210px;min-width:140px;border-right:1px solid var(--border);
  background:var(--bg2);display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}
#tree-head{display:flex;align-items:center;justify-content:space-between;
  padding:5px 8px;border-bottom:1px solid var(--border);flex-shrink:0}
#tree-head span{font-size:10px;letter-spacing:1px;color:var(--dim);text-transform:uppercase}
#tree-btns{display:flex;gap:3px}
#tree-scroll{flex:1;overflow-y:auto;padding:2px 0}

.tn{display:flex;align-items:center;gap:4px;padding:4px 8px;
  cursor:pointer;transition:.1s;user-select:none;position:relative}
.tn:hover{background:var(--bg3)}
.tn.sel{background:var(--cyan3)!important}
.tn.sel .tn-name{color:var(--cyan)}
.tn-icon{font-size:12px;width:15px;text-align:center;flex-shrink:0}
.tn-name{flex:1;font-size:12px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.tn-name.d{color:var(--amber)}
.tn-sz{font-size:10px;color:var(--dim);white-space:nowrap}
.tn-more{display:none;background:none;border:none;color:var(--dim);
  font-size:13px;padding:0 2px;cursor:pointer;line-height:1;text-transform:none}
.tn:hover .tn-more{display:block}
.tn-more:hover{color:var(--text)!important;border-color:transparent!important}
.ch{padding-left:12px}
.ch.hide{display:none}

/* editor pane */
#editor-pane{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}
#cm-wrap{flex:1;overflow:hidden;position:relative;display:none}
.CodeMirror{height:100%!important;font-family:'Inconsolata',monospace!important;
  font-size:13px!important;line-height:1.65!important;background:#1a1a2e!important}
.CodeMirror-gutters{background:#12121e!important;border-right:1px solid var(--border)!important}
.CodeMirror-linenumber{color:var(--dim)!important}
.CodeMirror-scroll{padding-bottom:30px}

#welcome{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:14px;padding:30px;text-align:center}
.w-logo{font-family:'VT323',monospace;font-size:52px;color:var(--cyan);text-shadow:0 0 20px var(--cyan)}
.w-sub{color:var(--dim);font-size:12px;line-height:2.2}
.w-key{display:inline-block;background:var(--bg3);border:1px solid var(--border);
  padding:1px 7px;font-size:11px;color:var(--text)}

/* status bar */
#statusbar{display:flex;align-items:center;gap:10px;padding:2px 10px;
  border-top:1px solid var(--border);background:var(--bg2);flex-shrink:0;
  font-size:11px;color:var(--dim)}
#statusbar span{color:var(--text)}
#statusbar a{color:var(--cyan2);text-decoration:none;cursor:pointer;margin-left:auto;font-size:11px}

/* context menu */
#ctx{position:fixed;display:none;background:var(--bg3);border:1px solid var(--border);
  z-index:8000;min-width:140px;box-shadow:0 6px 24px rgba(0,0,0,.7)}
.ci{padding:7px 14px;cursor:pointer;font-size:12px;transition:.1s}
.ci:hover{background:var(--cyan3);color:var(--cyan)}
.ci.d:hover{background:#2a0010;color:var(--red)}
.csep{height:1px;background:var(--border);margin:2px 0}

/* modal */
#mover{position:fixed;inset:0;background:rgba(0,0,0,.75);
  display:none;align-items:center;justify-content:center;z-index:9500}
#mbox{background:var(--bg3);border:1px solid var(--cyan2);padding:20px;
  min-width:260px;max-width:92vw;box-shadow:0 0 30px rgba(0,229,255,.12)}
#mbox h3{color:var(--cyan);font-family:'VT323',monospace;font-size:20px;
  letter-spacing:2px;margin-bottom:12px}
#minput{width:100%;background:var(--bg2);border:1px solid var(--border);
  color:var(--text);font-family:'Inconsolata',monospace;font-size:13px;
  padding:8px;outline:none;margin-bottom:12px;caret-color:var(--cyan)}
#minput:focus{border-color:var(--cyan2)}
.mbtns{display:flex;gap:8px;justify-content:flex-end}

/* shell overlay */
#shell{position:fixed;inset:0;background:var(--bg);z-index:500;
  flex-direction:column;display:none}
#shell.on{display:flex}
#sh-head{display:flex;align-items:center;justify-content:space-between;
  padding:5px 12px;border-bottom:1px solid var(--border);background:var(--bg2)}
#sh-out{flex:1;overflow-y:auto;padding:12px;background:var(--bg);
  white-space:pre-wrap;word-break:break-all;color:var(--green);font-size:12px;line-height:1.7}
#sh-row{display:flex;align-items:center;gap:6px;padding:6px 10px;
  border-top:1px solid var(--border);background:var(--bg2)}
.prompt{color:var(--cyan);text-shadow:0 0 6px var(--cyan);white-space:nowrap;font-size:13px;flex-shrink:0}
#sh-in{flex:1;background:transparent;border:none;color:var(--green);
  font-family:'Inconsolata',monospace;font-size:13px;outline:none;caret-color:var(--cyan)}
#sh-hints{display:flex;flex-wrap:wrap;gap:4px;padding:4px 10px 6px;
  background:var(--bg2);border-top:1px solid var(--border)}
.hint{background:var(--bg3);border:1px solid var(--dim2);color:var(--dim);
  padding:2px 7px;font-size:11px;cursor:pointer}
.hint:active{background:var(--cyan3);color:var(--cyan)}

/* sys overlay */
#sysv{position:fixed;inset:0;background:var(--bg);z-index:500;
  flex-direction:column;display:none}
#sysv.on{display:flex}
#sys-head{display:flex;align-items:center;justify-content:space-between;
  padding:5px 12px;border-bottom:1px solid var(--border);background:var(--bg2)}
#sys-body{flex:1;overflow-y:auto;padding:12px;
  display:grid;grid-template-columns:1fr 1fr;gap:8px;align-content:start}
.sc{background:var(--bg2);border:1px solid var(--border);padding:10px}
.sc .l{font-size:10px;letter-spacing:1px;color:var(--dim);text-transform:uppercase;margin-bottom:4px}
.sc .v{color:var(--cyan);font-size:15px;text-shadow:0 0 6px var(--cyan);word-break:break-all}
#sys-foot{padding:7px 12px;border-top:1px solid var(--border);background:var(--bg2)}

::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--dim2)}
</style>
</head>
<body>

<!-- IDE -->
<div id="ide">
  <header>
    <div class="logo">Q10<em>:</em>IDE</div>
    <div id="file-title">// select or create a file</div>
    <div id="save-st"></div>
    <div id="clock">--:--:--</div>
    <div class="dot"></div>
  </header>
  <div id="toolbar">
    <button class="pri" onclick="saveFile()">💾 Save</button>
    <button onclick="newFileDlg()">＋ File</button>
    <button onclick="newDirDlg()">＋ Dir</button>
    <div class="sep"></div>
    <button class="amb" onclick="openShell()">⚡ Shell</button>
    <button onclick="openSys()">📊 Sys</button>
    <div class="sep"></div>
    <button class="dan" onclick="closeFile()">✕ Close</button>
  </div>
  <div id="body">
    <div id="tree-panel">
      <div id="tree-head">
        <span>Explorer</span>
        <div id="tree-btns">
          <button class="sm" onclick="newFileDlg()" title="New file">+F</button>
          <button class="sm" onclick="newDirDlg()" title="New dir">+D</button>
          <button class="sm" onclick="refreshTree()" title="Refresh">↺</button>
        </div>
      </div>
      <div id="tree-scroll"></div>
    </div>
    <div id="editor-pane">
      <div id="welcome">
        <div class="w-logo">Q10:IDE</div>
        <div class="w-sub">
          Open a file from the tree to start editing.<br>
          <span class="w-key">+F</span> new file &nbsp;
          <span class="w-key">+D</span> new folder &nbsp;
          <span class="w-key">Ctrl+S</span> save<br>
          Right-click any file for rename / delete
        </div>
      </div>
      <div id="cm-wrap"><textarea id="cm-ta"></textarea></div>
    </div>
  </div>
  <div id="statusbar">
    <div>Lang: <span id="sb-lang">—</span></div>
    <div>Ln: <span id="sb-ln">—</span></div>
    <div>Col: <span id="sb-col">—</span></div>
    <div>Size: <span id="sb-sz">—</span></div>
    <a onclick="openShell()">⚡ shell</a>
  </div>
</div>

<!-- SHELL -->
<div id="shell">
  <div id="sh-head">
    <div class="logo" style="font-size:17px">Q10<em>:</em>SHELL</div>
    <button onclick="closeShell()">✕ IDE</button>
  </div>
  <div id="sh-out">// permitted: ls pwd whoami date uname df uptime ps ifconfig cat head tail&#10;</div>
  <div id="sh-row">
    <span class="prompt">bb$&nbsp;</span>
    <input id="sh-in" type="text" placeholder="command..." autocomplete="off" spellcheck="false">
    <button onclick="runCmd()">RUN</button>
  </div>
  <div id="sh-hints"></div>
</div>

<!-- SYS -->
<div id="sysv">
  <div id="sys-head">
    <div class="logo" style="font-size:17px">Q10<em>:</em>SYS</div>
    <button onclick="closeSys()">✕ IDE</button>
  </div>
  <div id="sys-body">
    <div class="sc"><div class="l">Platform</div><div class="v" id="si-pl">…</div></div>
    <div class="sc"><div class="l">Machine</div><div class="v" id="si-ma">…</div></div>
    <div class="sc"><div class="l">Python</div><div class="v" id="si-py">…</div></div>
    <div class="sc"><div class="l">Node</div><div class="v" id="si-no">…</div></div>
    <div class="sc"><div class="l">Uptime</div><div class="v" id="si-up">…</div></div>
    <div class="sc"><div class="l">Mem Used</div><div class="v" id="si-mu">…</div></div>
    <div class="sc"><div class="l">Mem Free</div><div class="v" id="si-mf">…</div></div>
    <div class="sc"><div class="l">Time</div><div class="v" id="si-ti">…</div></div>
  </div>
  <div id="sys-foot"><button onclick="loadSys()">[ REFRESH ]</button></div>
</div>

<!-- CTX MENU -->
<div id="ctx"></div>

<!-- MODAL -->
<div id="mover">
  <div id="mbox">
    <h3 id="mtitle">INPUT</h3>
    <input id="minput" type="text" autocomplete="off" spellcheck="false">
    <div class="mbtns">
      <button onclick="mCancel()">Cancel</button>
      <button class="pri" onclick="mOK()">OK</button>
    </div>
  </div>
</div>

<script>
// ── globals
var cm = null, curRel = null, mCB = null;
var treeData = [], collapsed = {};
var shHist = [], shIdx = -1;
var ctxRel = null, ctxType = null;

// ── clock
setInterval(function(){
  var n=new Date();
  document.getElementById('clock').textContent=n.toTimeString().slice(0,8);
},1000);

// ══════════════════ CODEMIRROR ══════════════════
function initCM(){
  if(cm) return;
  cm = CodeMirror.fromTextArea(document.getElementById('cm-ta'),{
    theme:'dracula', lineNumbers:true, matchBrackets:true,
    autoCloseBrackets:true, styleActiveLine:true,
    indentUnit:4, tabSize:4, indentWithTabs:false,
    extraKeys:{
      'Ctrl-S':function(){ saveFile(); },
      'Tab':function(c){
        if(c.somethingSelected()) c.indentSelection('add');
        else c.replaceSelection('    ','end');
      }
    }
  });
  cm.on('cursorActivity', updateSB);
  cm.on('change', function(){ updateSB(); setSt('',''); });
}

function modeFor(name){
  var e=(name||'').split('.').pop().toLowerCase();
  return {py:'python',js:'javascript',json:'javascript',
    html:'htmlmixed',htm:'htmlmixed',css:'css',
    sh:'shell',bash:'shell'}[e]||'null';
}

// ══════════════════ FILE OPS ══════════════════
async function openFile(rel){
  var r=await fetch('/api/read?path='+encodeURIComponent(rel));
  var d=await r.json();
  if(d.error){alert('Cannot open: '+d.error);return;}
  curRel=rel;
  var ft=document.getElementById('file-title');
  ft.textContent='~/'+rel; ft.className='active';
  document.getElementById('welcome').style.display='none';
  document.getElementById('cm-wrap').style.display='block';
  initCM();
  var mode=modeFor(rel.split('/').pop());
  cm.setOption('mode',mode);
  cm.setValue(d.content);
  cm.clearHistory();
  cm.focus();
  document.getElementById('sb-lang').textContent=mode==='null'?'text':mode;
  document.getElementById('sb-sz').textContent=fmtN(d.content.length);
  setSt('','');
  markTree(rel);
}

async function saveFile(){
  if(!curRel){setSt('No file open','err');return;}
  var content=cm?cm.getValue():'';
  var r=await fetch('/api/write',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:curRel,content:content})});
  var d=await r.json();
  if(d.error) setSt('Err: '+d.error,'err');
  else{
    setSt('Saved '+new Date().toTimeString().slice(0,5),'ok');
    document.getElementById('sb-sz').textContent=fmtN(content.length);
  }
}

function closeFile(){
  curRel=null;
  var ft=document.getElementById('file-title');
  ft.textContent='// select or create a file'; ft.className='';
  document.getElementById('welcome').style.display='';
  document.getElementById('cm-wrap').style.display='none';
  if(cm) cm.setValue('');
  setSt('','');
  ['sb-lang','sb-ln','sb-col','sb-sz'].forEach(function(id){
    document.getElementById(id).textContent='—';
  });
  markTree(null);
}

function setSt(msg,cls){
  var e=document.getElementById('save-st');
  e.textContent=msg; e.className=cls;
}

function updateSB(){
  if(!cm) return;
  var c=cm.getCursor();
  document.getElementById('sb-ln').textContent=cm.lineCount();
  document.getElementById('sb-col').textContent=c.ch+1;
}

function fmtN(n){
  if(n<1024) return n+'B';
  if(n<1048576) return Math.round(n/1024)+'KB';
  return (n/1048576).toFixed(1)+'MB';
}

// ══════════════════ TREE ══════════════════
async function refreshTree(){
  var r=await fetch('/api/tree');
  treeData=await r.json();
  renderTree();
}

function renderTree(){
  var h=renderNodes(treeData,0);
  document.getElementById('tree-scroll').innerHTML=
    h||'<div style="color:var(--dim);padding:10px;font-size:11px">// empty</div>';
}

function renderNodes(nodes,depth){
  var out='';
  for(var i=0;i<nodes.length;i++){
    var n=nodes[i];
    var pl=(8+depth*12)+'px';
    var isD=n.type==='dir';
    var icon=isD?(collapsed[n.rel]?'▶':'▼'):fIcon(n.name);
    var sel=(n.rel===curRel)?' sel':'';
    out+='<div class="tn'+sel+'" style="padding-left:'+pl+'"'
      +' data-rel="'+esc(n.rel)+'"'
      +' onclick="tnClick(event,\''+esc2(n.rel)+'\',\''+n.type+'\')"'
      +' oncontextmenu="showCtx(event,\''+esc2(n.rel)+'\',\''+n.type+'\')">'
      +'<span class="tn-icon">'+icon+'</span>'
      +'<span class="tn-name'+(isD?' d':'')+'" title="'+esc(n.rel)+'">'+esc(n.name)+'</span>'
      +(n.size?'<span class="tn-sz">'+esc(n.size)+'</span>':'')
      +'<button class="tn-more" onclick="showCtx(event,\''+esc2(n.rel)+'\',\''+n.type+'\');event.stopPropagation()">⋯</button>'
      +'</div>';
    if(isD&&n.children&&!collapsed[n.rel]){
      out+='<div class="ch">'+renderNodes(n.children,depth+1)+'</div>';
    }
  }
  return out;
}

function tnClick(e,rel,type){
  if(type==='dir'){ collapsed[rel]=!collapsed[rel]; renderTree(); }
  else openFile(rel);
}

function markTree(rel){
  document.querySelectorAll('.tn').forEach(function(el){
    el.classList.toggle('sel',el.dataset.rel===rel);
  });
}

function fIcon(name){
  var e=name.split('.').pop().toLowerCase();
  return {py:'🐍',js:'📜',json:'📋',html:'🌐',htm:'🌐',css:'🎨',
    md:'📝',txt:'📄',sh:'⚙️',log:'📃',jpg:'🖼',png:'🖼'}[e]||'📄';
}

// ══════════════════ CTX MENU ══════════════════
function showCtx(e,rel,type){
  e.preventDefault(); e.stopPropagation();
  ctxRel=rel; ctxType=type;
  var isD=type==='dir';
  var m=document.getElementById('ctx');
  m.innerHTML=
    (isD?'':'<div class="ci" onclick="ctxOpen()">📂 Open</div>')
    +'<div class="ci" onclick="ctxRename()">✏️ Rename</div>'
    +(isD?'<div class="ci" onclick="ctxNF()">＋ New file here</div>':'')
    +'<div class="csep"></div>'
    +'<div class="ci d" onclick="ctxDel()">🗑 Delete</div>';
  m.style.display='block';
  m.style.left=Math.min(e.clientX,window.innerWidth-155)+'px';
  m.style.top=Math.min(e.clientY,window.innerHeight-120)+'px';
}
function closeCtx(){document.getElementById('ctx').style.display='none';}
document.addEventListener('click',closeCtx);

function ctxOpen(){if(ctxRel)openFile(ctxRel);closeCtx();}
function ctxRename(){
  var r=ctxRel,old=r.split('/').pop(); closeCtx();
  modal('Rename',old,async function(n){
    if(!n||n===old)return;
    var res=await fetch('/api/rename',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:r,name:n})});
    var d=await res.json();
    if(d.error)alert('Error: '+d.error); else refreshTree();
  });
}
function ctxDel(){
  var r=ctxRel; closeCtx();
  if(!confirm('Delete "'+r+'"?'))return;
  fetch('/api/delete',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:r})})
  .then(function(res){return res.json();})
  .then(function(d){
    if(d.error)alert('Error: '+d.error);
    else{if(curRel===r)closeFile();refreshTree();}
  });
}
function ctxNF(){
  var dir=ctxRel; closeCtx();
  modal('New file in '+dir,'',async function(n){
    if(!n)return;
    var rel=dir+'/'+n;
    var res=await fetch('/api/create',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:rel,kind:'file'})});
    var d=await res.json();
    if(d.error)alert('Error: '+d.error);
    else{await refreshTree();openFile(rel);}
  });
}

// ══════════════════ NEW FILE / DIR ══════════════════
function newFileDlg(){
  modal('New file path (e.g. myproject/app.py)','',async function(rel){
    if(!rel)return;
    var r=await fetch('/api/create',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:rel,kind:'file'})});
    var d=await r.json();
    if(d.error)alert('Error: '+d.error);
    else{await refreshTree();openFile(rel);}
  });
}
function newDirDlg(){
  modal('New folder path','',async function(rel){
    if(!rel)return;
    var r=await fetch('/api/create',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:rel,kind:'dir'})});
    var d=await r.json();
    if(d.error)alert('Error: '+d.error);
    else refreshTree();
  });
}

// ══════════════════ MODAL ══════════════════
function modal(title,def,cb){
  mCB=cb;
  document.getElementById('mtitle').textContent=title;
  var inp=document.getElementById('minput');
  inp.value=def||'';
  document.getElementById('mover').style.display='flex';
  setTimeout(function(){inp.focus();inp.select();},40);
}
function mCancel(){document.getElementById('mover').style.display='none';mCB=null;}
function mOK(){
  var v=document.getElementById('minput').value.trim();
  document.getElementById('mover').style.display='none';
  if(mCB)mCB(v); mCB=null;
}
document.getElementById('minput').addEventListener('keydown',function(e){
  if(e.key==='Enter')mOK();
  if(e.key==='Escape')mCancel();
});

// ══════════════════ SHELL ══════════════════
var SH_CMDS=['ls -la','pwd','whoami','uname -a','df -h','uptime','ps','ifconfig','date','cat'];
function openShell(){
  document.getElementById('shell').classList.add('on');
  document.getElementById('sysv').classList.remove('on');
  buildHints();
  document.getElementById('sh-in').focus();
}
function closeShell(){document.getElementById('shell').classList.remove('on');}
function buildHints(){
  var h='';
  for(var i=0;i<SH_CMDS.length;i++)
    h+='<div class="hint" onclick="setSHCmd(\''+esc2(SH_CMDS[i])+'\')">'+esc(SH_CMDS[i])+'</div>';
  document.getElementById('sh-hints').innerHTML=h;
}
function setSHCmd(c){document.getElementById('sh-in').value=c;}
async function runCmd(){
  var inp=document.getElementById('sh-in');
  var cmd=inp.value.trim(); if(!cmd)return;
  shHist.unshift(cmd); shIdx=-1;
  var out=document.getElementById('sh-out');
  out.textContent+='\nbb$ '+cmd+'\n';
  var r=await fetch('/api/shell',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({cmd:cmd})});
  var d=await r.json();
  out.textContent+=d.output+'\n';
  out.scrollTop=out.scrollHeight;
  inp.value='';
}
document.getElementById('sh-in').addEventListener('keydown',function(e){
  if(e.key==='Enter'){runCmd();return;}
  if(e.key==='ArrowUp'){e.preventDefault();
    if(shIdx<shHist.length-1){shIdx++;this.value=shHist[shIdx];}}
  if(e.key==='ArrowDown'){e.preventDefault();
    if(shIdx>0){shIdx--;this.value=shHist[shIdx];}
    else{shIdx=-1;this.value='';}}
});

// ══════════════════ SYS ══════════════════
function openSys(){
  document.getElementById('sysv').classList.add('on');
  document.getElementById('shell').classList.remove('on');
  loadSys();
}
function closeSys(){document.getElementById('sysv').classList.remove('on');}
async function loadSys(){
  var r=await fetch('/api/sysinfo');
  var d=await r.json();
  document.getElementById('si-pl').textContent=d.platform||'?';
  document.getElementById('si-ma').textContent=d.machine||'?';
  document.getElementById('si-py').textContent=d.python||'?';
  document.getElementById('si-no').textContent=d.node||'?';
  document.getElementById('si-up').textContent=d.uptime||'?';
  document.getElementById('si-mu').textContent=(d.mem_used||'?')+' / '+(d.mem_total||'?');
  document.getElementById('si-mf').textContent=d.mem_free||'?';
  document.getElementById('si-ti').textContent=d.time||'?';
}

// ══════════════════ GLOBAL KEYS ══════════════════
document.addEventListener('keydown',function(e){
  if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();saveFile();}
  if(e.key==='Escape'){
    mCancel();
    document.getElementById('shell').classList.remove('on');
    document.getElementById('sysv').classList.remove('on');
  }
});

// ══════════════════ UTILS ══════════════════
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function esc2(s){return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'");}

// ══════════════════ INIT ══════════════════
refreshTree();
</script>
</body>
</html>
"""

# =============================================================================
#  HTTP handler
# =============================================================================
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        sys.stdout.write('[{}] {}\n'.format(
            datetime.datetime.now().strftime('%H:%M:%S'), fmt % args))

    def send_json(self, data, code=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',   'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type',   'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(n) if n else b''

    def do_GET(self):
        try:
            p  = urlparse(self.path)
            qs = parse_qs(p.query)
            if   p.path == '/':            self.send_html(HTML)
            elif p.path == '/api/sysinfo': self.send_json(sysinfo())
            elif p.path == '/api/tree':    self.send_json(tree(''))
            elif p.path == '/api/read':
                rel = qs.get('path',[''])[0]
                c, e = read_file(rel)
                self.send_json({'error':e} if e else {'content':c})
            else:
                self.send_response(404); self.end_headers()
        except Exception:
            traceback.print_exc()
            self.send_response(500); self.end_headers()

    def do_POST(self):
        try:
            p    = urlparse(self.path)
            raw  = self.body()
            data = json.loads(raw.decode('utf-8')) if raw else {}

            if   p.path == '/api/write':
                e = write_file(data.get('path',''), data.get('content',''))
                self.send_json({'error':e} if e else {'ok':True})
            elif p.path == '/api/create':
                e = create_node(data.get('path',''), data.get('kind','file'))
                self.send_json({'error':e} if e else {'ok':True})
            elif p.path == '/api/rename':
                e = rename_node(data.get('path',''), data.get('name',''))
                self.send_json({'error':e} if e else {'ok':True})
            elif p.path == '/api/delete':
                e = delete_node(data.get('path',''))
                self.send_json({'error':e} if e else {'ok':True})
            elif p.path == '/api/shell':
                self.send_json({'output': run_cmd(data.get('cmd',''))})
            else:
                self.send_response(404); self.end_headers()
        except Exception:
            traceback.print_exc()
            self.send_response(500); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print('=' * 46)
    print('  q10ide  |  port {}  |  root: {}'.format(PORT, ROOT))
    print('  http://<Q10-IP>:{}'.format(PORT))
    print('  stop: Ctrl+C  (metamode -> c -> c on Q10)')
    print('=' * 46)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[q10ide] stopped.')
