# q10flask — POC Flask server for BlackBerry Q10 / Term49

A terminal-aesthetic web app: system info, sticky notes, and a
whitelisted shell runner. Accessed from any browser on your LAN.

## Setup (on your PC)

```bash
python vendor_setup.py
```

This downloads all Flask dependencies as pure-Python source into `vendor/`.
No compiled .so files — should work on BB10's QNX ARM environment.

## Deploy to Q10

Copy the whole folder over SCP:

```bash
scp -r q10flask/ user@<Q10-IP>:/accounts/1000/shared/misc/
```

Or clone directly on the Q10 if you have git via BerryMuch.

## Run on Q10 (in Term49)

```bash
cd q10flask
python app.py
# or if python3 specifically:
python3 app.py
```

To keep it running after you switch away from Term49:

```bash
setsid python app.py &
```

## Access

From any browser on the same WiFi:

```
http://<Q10-IP>:5000
```

Find your Q10's IP with:
```bash
ifconfig
```

## Features

- **SYS tab** — live platform, memory, uptime info
- **NOTES tab** — persistent sticky notes (saved to notes.json)
- **SHELL tab** — run whitelisted commands (ls, pwd, df, ps, etc.)

## Change port

```bash
PORT=8080 python app.py
```
