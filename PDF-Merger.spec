# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정. Windows exe와 macOS .app을 같은 파일로 만든다.

    uv run pyinstaller --noconfirm PDF-Merger.spec
"""

import os
import sys
import tomllib

ROOT = SPECPATH  # 이 spec 파일이 있는 폴더 (PyInstaller가 넣어 주는 변수)
ASSETS = os.path.join(ROOT, "src", "pdf_merger", "assets")
APP_NAME = "PDF-Merger"

with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
    VERSION = tomllib.load(f)["project"]["version"]

a = Analysis(
    [os.path.join(ROOT, "src", "pdf_merger", "__main__.py")],
    datas=[(os.path.join(ASSETS, "icon.png"), "pdf_merger/assets")],  # 창 아이콘
    excludes=[
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtPdf",
        # Pillow는 아이콘 생성 스크립트에만 필요하다. pypdf가 있으면 가져다 쓰지만 병합에는 쓰지 않는다.
        "PIL",
        "tkinter",
    ],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    # macOS는 폴더 형태(onedir)로 모은 뒤 .app 번들로 감싼다. onefile은 .app에 권장되지 않는다.
    exe = EXE(pyz, a.scripts, exclude_binaries=True, name=APP_NAME, console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=os.path.join(ASSETS, "icon.icns"),
        bundle_identifier="com.hoyeongjeon.pdf-merger",
        info_plist={
            "CFBundleDisplayName": "PDF 병합기",
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            # PDF를 받을 수 있는 앱으로 등록해서 Dock 아이콘에 끌어다 놓을 수 있게 한다.
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "PDF",
                    "CFBundleTypeRole": "Viewer",
                    "LSItemContentTypes": ["com.adobe.pdf"],
                    "LSHandlerRank": "Alternate",
                }
            ],
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name=APP_NAME,
        console=False,
        icon=os.path.join(ASSETS, "icon.ico"),
    )
