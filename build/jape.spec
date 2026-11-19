# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PyJape. make_dist.py builds the native engine into
../resources first; this bundles the app + the whole resources/ folder.
Produces a one-folder app (and a .app bundle on macOS)."""
import os
import sys

HERE = os.path.abspath(SPECPATH)                 # <repo>/build
PYAPP = os.path.dirname(HERE)
RESOURCES = os.path.join(PYAPP, 'resources')     # jape-engine[.exe] + examples/


def _python_license():
    """The licence of the Python being bundled (PSF + notices for libraries that
    ship with Python), copied into licenses/python/. Windows keeps it in the
    install root; macOS and Linux keep it in the stdlib folder."""
    import sysconfig
    for p in (os.path.join(sys.base_prefix, 'LICENSE.txt'),
              os.path.join(sysconfig.get_path('stdlib'), 'LICENSE.txt')):
        if os.path.exists(p):
            return [(p, os.path.join('licenses', 'python'))]
    print('WARNING: could not find Python\'s LICENSE.txt; it will not be bundled')
    return []

a = Analysis(
    [os.path.join(PYAPP, 'run.py')],
    pathex=[PYAPP],
    binaries=[],
    datas=[(RESOURCES, 'resources'),             # -> _internal/resources/{jape-engine,examples}
           (os.path.join(PYAPP, 'LICENSE'), '.'),    # GPL text ships with the binaries
           (os.path.join(PYAPP, 'THIRD_PARTY_NOTICES.md'), '.')] + _python_license(),
    hiddenimports=['jape', 'jape.app', 'jape.engine', 'jape.protocol', 'jape.logic'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['numpy', 'pandas', 'PIL', 'matplotlib', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='PyJape',
    console=False,                               # windowed; errors go to a dialog
    icon=(os.path.join(HERE, 'icon.ico') if os.path.exists(os.path.join(HERE, 'icon.ico')) else None),
)
coll = COLLECT(exe, a.binaries, a.datas, name='PyJape')

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='PyJape.app',
        bundle_identifier='io.github.hamzabandukara.pyjape',
        icon=(os.path.join(HERE, 'icon.icns') if os.path.exists(os.path.join(HERE, 'icon.icns')) else None),
        info_plist={'NSHighResolutionCapable': True},
    )
