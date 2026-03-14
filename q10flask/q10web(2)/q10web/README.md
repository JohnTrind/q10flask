# q10web

Zero-dependency web file manager for BlackBerry Q10 / BB10.
Pure Python stdlib — works on Python 2.7 and Python 3.2+.
No pip, no packages, no vendor folder needed.

## Run

```bash
python server.py
# or background it:
setsid python server.py &
```

## Access

From any browser on the same WiFi:
```
http://<Q10-IP>:5000
```

Find your IP with:
```bash
ifconfig
```

## Features

- **SYS** — platform, memory, uptime, Python version
- **FILES** — browse the home directory, tap to navigate folders
- **EDIT** — tap any text file in FILES to open it, edit, save
- **SHELL** — run whitelisted commands with history (arrow keys)

## Config

Edit the top of server.py:

```python
PORT  = 5000          # change port
ROOT  = os.path.expanduser('~')  # change browsable root
MAX_EDIT_BYTES = 128 * 1024      # max editable file size
```

## Stop

In Term49:  metamode → c → c  (sends Ctrl+C)
