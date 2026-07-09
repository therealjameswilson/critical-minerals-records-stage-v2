#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Start Tool — double-clickable launcher for the Records Stage HTML tool.
#
# What this does:
#   1. cd's to the repo root (where this file lives).
#   2. Starts local_server.py, which exposes /ping + /summarize + /nara/search
#      + /nara/fetch on http://localhost:5757.
#   3. The server auto-opens records-stage.html in your default browser.
#
# What you do:
#   • Double-click this file from Finder. A Terminal window will pop up and
#     show the server's progress. When you see "Listening at ..." the tool
#     is ready (the browser tab opens automatically).
#   • When you're done, close the Terminal window — that stops the server.
#
# First-time setup (only needed once):
#   • If macOS says "Start Tool.command cannot be opened because it is from
#     an unidentified developer" — right-click the file → Open → Open again.
#     macOS will remember the choice afterwards.
#   • If you see "permission denied", open Terminal and run:
#         chmod +x "$(pwd)/Start Tool.command"
#
# Requirements:
#   • Python 3 (install from https://python.org if missing).
#   • pip install flask flask-cors
#     (optional: + transformers torch sentencepiece for the AI summarizer).
#   • If using NARA: save your Catalog API key to .nara_key in this folder.
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

PY=""
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo
  echo "  ✗  No Python found on this Mac. Install Python 3 from https://python.org"
  echo "     then try again."
  echo
  echo "  Press any key to close this window."
  read -n 1 -s -r
  exit 1
fi

echo
echo "  Starting Toolkit Local Server…"
echo "  Repo: $(pwd)"
echo "  Python: $($PY --version 2>&1)"
echo

exec "$PY" local_server.py
