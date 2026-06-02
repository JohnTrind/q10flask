# q10flask

Flask-based web tools for the **BlackBerry Q10**, running on BB10's QNX ARM environment via [Term49](https://github.com/stuartleeks/Term49).

## Projects

### q10flask/
Terminal-aesthetic web app served from the Q10 itself: system info, sticky notes, and a whitelisted shell runner. All Flask dependencies are vendored as pure Python — no compiled `.so` files needed.

```bash
cd q10flask
python vendor_setup.py   # download deps into vendor/
python app.py            # start server on :5000
```

Deploy to the device:
```bash
scp -r q10flask/ user@<Q10-IP>:/accounts/1000/shared/misc/
```

### dungeon/
**DELVE** — a curses roguelike built for the Q10 keyboard. Pure Python stdlib, zero dependencies.

```bash
python q10flask/dungeon/dungeon.py
```

Keys: arrows or `hjkl`/`wasd` · `i` inventory · `g` grab · `.` wait · `q` quit

### q10web/
Lighter standalone Flask server — single `server.py`, alternative layout. Drop-in alternative to q10flask.

```bash
python "q10flask/q10web(2)/q10web/server.py"
```

## Access

From any browser on the same WiFi once the server is running:
```
http://<Q10-IP>:5000
```
