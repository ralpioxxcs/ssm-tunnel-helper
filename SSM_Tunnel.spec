# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['ssm_tunnel_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('VERSION', '.')],
    hiddenimports=[
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── 사용하지 않는 Python 패키지 ─────────────────────────────────────
        'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas',
        'PIL', 'cv2', 'wx', 'gi', 'IPython',
        'setuptools', 'distutils', 'unittest', 'doctest',
        'pdb', 'profile', 'cProfile', 'pstats', 'timeit', 'turtle',
        # ── 사용하지 않는 PyQt5 모듈 ─────────────────────────────────────────
        'PyQt5.QtBluetooth',    'PyQt5.QtDBus',         'PyQt5.QtDesigner',
        'PyQt5.QtHelp',         'PyQt5.QtLocation',     'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets', 'PyQt5.QtNfc',     'PyQt5.QtNetwork',
        'PyQt5.QtOpenGL',       'PyQt5.QtPositioning',  'PyQt5.QtPrintSupport',
        'PyQt5.QtQml',          'PyQt5.QtQuick',        'PyQt5.QtQuickWidgets',
        'PyQt5.QtRemoteObjects','PyQt5.QtSensors',      'PyQt5.QtSerialPort',
        'PyQt5.QtSql',          'PyQt5.QtSvg',          'PyQt5.QtTest',
        'PyQt5.QtTextToSpeech', 'PyQt5.QtWebChannel',
        'PyQt5.QtWebEngine',    'PyQt5.QtWebEngineCore','PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebSockets',   'PyQt5.QtX11Extras',    'PyQt5.QtXml',
        'PyQt5.QtXmlPatterns',  'PyQt5.Qt3DAnimation',  'PyQt5.Qt3DCore',
        'PyQt5.Qt3DExtras',     'PyQt5.Qt3DInput',      'PyQt5.Qt3DLogic',
        'PyQt5.Qt3DRender',     'PyQt5.QtDataVisualization', 'PyQt5.QtChart',
        'PyQt5.QtQuickControls2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SSM Tunnel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,        # 디버그 심볼 제거
    upx=False,         # macOS: UPX는 코드서명 깨짐
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,        # 디버그 심볼 제거
    upx=False,
    upx_exclude=[],
    name='SSM Tunnel',
)

# ── Post-processing: 불필요한 Qt 라이브러리 제거 (~17MB) ──────────────────────
import os, shutil as _shutil

_base = os.path.join(DISTPATH, 'SSM Tunnel')
# PyInstaller 6.x → _internal 하위 디렉토리 사용
_internal = os.path.join(_base, '_internal')
_qt5 = os.path.join(_internal if os.path.isdir(_internal) else _base, 'PyQt5', 'Qt5')

_REMOVE_FRAMEWORKS = [
    'QtQuick', 'QtQml', 'QtQmlModels',   # QML 엔진 (8.7MB)
    'QtNetwork',                           # 네트워크 (1.4MB)
    'QtPrintSupport',                      # 인쇄 (0.35MB)
    'QtWebSockets',                        # WebSocket (0.21MB)
]

_lib_dir = os.path.join(_qt5, 'lib')
for _lib in _REMOVE_FRAMEWORKS:
    _p = os.path.join(_lib_dir, f'{_lib}.framework')
    if os.path.exists(_p):
        _shutil.rmtree(_p)
        print(f'  [slim] removed {_lib}.framework')

# Qt 번역 파일 전체 제거 — 앱 문자열은 직접 작성, Qt 내장 다이얼로그 번역 불필요 (5.8MB)
_trans = os.path.join(_qt5, 'translations')
if os.path.exists(_trans):
    _shutil.rmtree(_trans)
    print(f'  [slim] removed translations ({_trans})')

# ─────────────────────────────────────────────────────────────────────────────

app = BUNDLE(
    coll,
    name='SSM Tunnel.app',
    icon='icon.icns',
    bundle_identifier='com.internal.ssm-tunnel',
    info_plist={
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleShortVersionString': open('VERSION').read().strip(),
        'CFBundleVersion': open('VERSION').read().strip(),
        'LSMinimumSystemVersion': '12.0',
        'NSHumanReadableCopyright': '',
        'LSBackgroundOnly': False,
        'NSAppleEventsUsageDescription': 'SSM Tunnel이 시스템 통합을 위해 Apple Events를 사용합니다.',
    },
)
