#!/usr/bin/env python3
"""Build PyJape: compile the native Jape engine, then package the app.

Inputs (all in this repository):
  engine-src/   the OCaml engine sources
  resources/    the example logics (committed) + the native engine (built here)
  jape/ run.py  the Python/Tkinter app

Steps (run on each target OS — native code does not cross-compile):
  1. dune build the NATIVE engine  ->  resources/jape-engine[.exe]
  2. PyInstaller bundles the app + resources/  ->  build/dist/

Prereqs: OCaml 4.14.x + dune on PATH (opam; in CI: ocaml/setup-ocaml);
         Python 3.9+ with tkinter;  pip install pyinstaller

  python build/make_dist.py            # full build
  python build/make_dist.py --engine-only   # just build the native engine
  python build/make_dist.py --skip-engine   # reuse built engine, just package
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))     # <repo>/build
PYAPP = os.path.dirname(HERE)                          # <repo>
ENGINE_SRC = os.path.join(PYAPP, 'engine-src')
RESOURCES = os.path.join(PYAPP, 'resources')          # examples/ committed; engine built in here
IS_WIN = os.name == 'nt'
ENGINE_NAME = 'jape-engine.exe' if IS_WIN else 'jape-engine'


def run(cmd, **kw):
    print('  $', ' '.join(cmd))
    subprocess.run(cmd, check=True, **kw)


def build_engine():
    print('[1/2] building the native OCaml engine (dune)…')
    target = 'node_engine/engine_main.exe'          # dune targets use forward slashes
    # Run dune INSIDE the opam environment so ocamlc is on PATH even if the
    # switch isn't activated in this shell (the usual "ocamlc not found" error).
    if shutil.which('opam'):
        cmd = ['opam', 'exec', '--', 'dune', 'build', target]
    elif shutil.which('dune'):
        cmd = ['dune', 'build', target]
    else:
        sys.exit("ERROR: neither 'opam' nor 'dune' is on PATH.\n"
                 "  Install OCaml + opam, then:\n"
                 "    opam init -y && opam switch create 4.14.2 && opam install -y dune")
    try:
        run(cmd, cwd=ENGINE_SRC)
    except subprocess.CalledProcessError:
        win = (
            "  On WINDOWS you need opam 2.2+ (older opam is Unix-only):\n"
            "    winget install OCaml.opam\n"
            "    opam init\n    opam switch create 4.14.2\n    opam install dune\n"
            if IS_WIN else
            "  Set up OCaml once:\n"
            "    opam init -y\n    opam switch create 4.14.2\n    opam install -y dune\n")
        sys.exit(
            "\nERROR: the native engine did not build (usually: no OCaml 4.14 compiler).\n"
            + win +
            "  (OCaml 5 won't work — the engine uses Stream.)\n\n"
            "  EASIEST: don't build OCaml locally at all. Grab a prebuilt jape-engine%s from a\n"
            "  GitHub Actions '…-folder' artifact (in _internal\\resources\\), drop it into\n"
            "  resources/, and run:  python build/make_dist.py --skip-engine\n"
            "  (WSL can't help here — it builds a Linux binary, which a Windows app can't run.)"
            % ('.exe' if IS_WIN else ''))
    built = os.path.join(ENGINE_SRC, '_build', 'default', 'node_engine', 'engine_main.exe')
    if not os.path.exists(built):
        sys.exit('ERROR: engine build produced no binary at ' + built)
    os.makedirs(RESOURCES, exist_ok=True)
    dst = os.path.join(RESOURCES, ENGINE_NAME)
    shutil.copy2(built, dst)
    if not IS_WIN:
        os.chmod(dst, 0o755)
    print('      engine ->', dst, '(%.1f MB)' % (os.path.getsize(dst) / 1e6))


def build_app():
    print('[2/2] packaging with PyInstaller…')
    if not os.path.exists(os.path.join(RESOURCES, ENGINE_NAME)):
        sys.exit('ERROR: no native engine in resources/. Run without --skip-engine first.')
    try:
        import tkinter  # noqa: F401
    except Exception:
        sys.exit("ERROR: tkinter is not available in this Python.\n"
                 "  Linux: sudo apt install python3-tk.  Win/macOS: use the python.org build.")
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        sys.exit("ERROR: PyInstaller not installed.  pip install pyinstaller")
    run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
         '--distpath', os.path.join(HERE, 'dist'),
         '--workpath', os.path.join(HERE, 'work'),
         os.path.join(HERE, 'jape.spec')])
    print('\nDone. Distributable is in:', os.path.join(HERE, 'dist'))
    print('  (zip that folder to share it, or build an installer — see build/BUILD.md)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine-only', action='store_true', help='build the native engine only')
    ap.add_argument('--skip-engine', action='store_true', help='reuse the built engine, just package')
    args = ap.parse_args()
    if not args.skip_engine:
        build_engine()
    if args.engine_only:
        return
    build_app()


if __name__ == '__main__':
    main()
