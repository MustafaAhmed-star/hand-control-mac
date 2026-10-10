# PyInstaller spec for the macOS app. Build with ./build_mac.sh
from PyInstaller.utils.hooks import collect_all

mp_datas, mp_binaries, mp_hidden = collect_all("mediapipe")

a = Analysis(
    ["hand_control.py"],
    binaries=mp_binaries,
    datas=mp_datas + [("hand_landmarker.task", ".")],
    hiddenimports=mp_hidden,
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HandControl", console=False,
          icon="icon.png")
coll = COLLECT(exe, a.binaries, a.datas, name="HandControl")
app = BUNDLE(
    coll,
    name="HandControl.app",
    icon="icon.png",
    bundle_identifier="local.handcontrol",
    info_plist={
        "CFBundleShortVersionString": "1.1.0",
        "NSCameraUsageDescription": "Hand Control watches your hand through the camera to recognise gestures. "
                                    "Nothing is recorded or sent anywhere.",
        "NSAppleEventsUsageDescription": "Hand Control changes the system volume.",
        "NSHighResolutionCapable": True,
    },
)
