#!/usr/bin/env python3
"""One command: python3 apply_all.py  (patches ./index.html with both upgrades)"""
import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
target = os.path.join(here, 'index.html')
if not os.path.exists(target): sys.exit('Put your Trade Pulse Pro file here as index.html first.')
for script in ('patch_sync.py', 'patch_google_first.py', 'patch_image_hydrate.py', 'patch_multidevice.py'):
    subprocess.run([sys.executable, os.path.join(here, script), target], check=True)
print('Done. Commit index.html, config.js, .nojekyll and README.md to GitHub.')
