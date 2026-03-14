#!/usr/bin/env python3
"""
vendor_setup.py
Run this on your PC to download pure-Python Flask deps into ./vendor/
Then copy the whole q10flask/ folder to the Q10.

Usage:
    python vendor_setup.py
"""
import subprocess
import sys
import os

VENDOR_DIR = os.path.join(os.path.dirname(__file__), 'vendor')

# Pure-Python packages that should work on QNX ARM
PACKAGES = [
    'flask==3.0.3',
    'werkzeug==3.0.3',
    'jinja2==3.1.4',
    'click==8.1.7',
    'markupsafe==2.1.5',
    'itsdangerous==2.2.0',
    'blinker==1.8.2',
]

def main():
    os.makedirs(VENDOR_DIR, exist_ok=True)
    print(f"[*] Downloading pure-Python packages to {VENDOR_DIR}/")

    for pkg in PACKAGES:
        print(f"    -> {pkg}")
        subprocess.run([
            sys.executable, '-m', 'pip', 'download',
            pkg,
            '--dest', VENDOR_DIR,
            '--no-deps',
            '--no-binary', ':none:',  # source only = pure python = no .so files
        ], check=True, capture_output=True)

    # Unzip all the wheels/tarballs into vendor/
    print("[*] Unpacking into vendor/...")
    import zipfile, tarfile, glob

    for f in glob.glob(os.path.join(VENDOR_DIR, '*.whl')):
        with zipfile.ZipFile(f) as z:
            z.extractall(VENDOR_DIR)
        os.remove(f)

    for f in glob.glob(os.path.join(VENDOR_DIR, '*.tar.gz')):
        with tarfile.open(f) as t:
            # extract only the package source, not setup.py etc
            t.extractall(VENDOR_DIR)
        os.remove(f)

    print("[*] Done! Your folder is ready to copy to the Q10.")
    print()
    print("    Copy the entire q10flask/ folder to the device, then:")
    print("    $ cd q10flask")
    print("    $ python app.py")
    print()
    print("    Then on any device on the same WiFi, open:")
    print("    http://<Q10-IP>:5000")

if __name__ == '__main__':
    main()
