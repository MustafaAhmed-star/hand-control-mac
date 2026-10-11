#!/bin/bash
# Builds HandControl.app and installs it into Applications. Run on an Apple Silicon Mac.
# Pass --no-install to only build (used by the GitHub workflow).
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt pyinstaller==6.22.3

if [ ! -f hand_landmarker.task ]; then
  curl -fL -o hand_landmarker.task \
    https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
fi

.venv/bin/python -m unittest discover -s tests
.venv/bin/pyinstaller --noconfirm --clean HandControl.spec

# PyInstaller's ad-hoc signature is tied to this exact build, so macOS would
# forget the Accessibility and camera permissions after every update. Name the
# app by its bundle identifier instead, so permissions carry over to new versions.
codesign --force --sign - --identifier local.handcontrol \
  --requirements '=designated => identifier "local.handcontrol"' dist/HandControl.app
codesign --verify --deep --strict dist/HandControl.app
codesign --display --requirements - dist/HandControl.app

cd dist
rm -f HandControl-mac.zip
ditto -c -k --keepParent HandControl.app HandControl-mac.zip
echo "Built dist/HandControl.app and dist/HandControl-mac.zip"

# Install into Applications so it opens from Launchpad and Spotlight like any app.
if [ "${1:-}" != "--no-install" ]; then
  if ! ditto HandControl.app /Applications/HandControl.app 2>/dev/null; then
    mkdir -p ~/Applications
    ditto HandControl.app ~/Applications/HandControl.app
    echo "Installed to ~/Applications/HandControl.app"
  else
    echo "Installed to /Applications/HandControl.app"
  fi
fi
