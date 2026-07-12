#!/bin/bash
set -euo pipefail

Xvfb :99 -screen 0 1024x768x16 &
sleep 2

# The MT5 terminal itself needs to be running (logged into the demo/live
# account once interactively, per docs/deployment_ubuntu.md) for the
# rpyc_server's mt5.initialize()/login() calls to succeed.
wine "C:\\Program Files\\MetaTrader 5\\terminal64.exe" /portable &
sleep 10

# Xvfb (started above) is already running on $DISPLAY -- don't wrap this in
# xvfb-run too, or it tries to start a second server on the same display and
# fails with "Server is already active for display 99". Use the full path
# since bare `python` isn't reliably on Wine's PATH for non-interactive execs.
exec wine "C:\\Program Files\\Python311\\python.exe" /opt/rpyc_server.py
