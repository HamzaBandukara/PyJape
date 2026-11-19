#!/bin/bash
# PyJape — build the native engine from source and run it with Python (macOS).
#
# For anyone who wants to run PyJape from source. It installs the OCaml
# toolchain (once), compiles the native engine, and launches the app.
# Double-click this file in Finder, or run:  bash setup-macos.command
#
# Safe to re-run: it skips anything already installed. Pass --rebuild to force
# recompiling the engine.
set -euo pipefail

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Work from the repo root (this script lives in scripts/, one level down).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
say "Working in: $(pwd)"

# 1. C toolchain (Xcode Command Line Tools) — needed to compile OCaml.
if ! xcode-select -p >/dev/null 2>&1; then
  say "Installing Xcode Command Line Tools (a system dialog will open)…"
  xcode-select --install || true
  die "Finish the Command Line Tools install, then run this script again."
fi

# 2. opam (the OCaml package manager).
if ! command -v opam >/dev/null 2>&1; then
  say "Installing opam…"
  bash -c 'sh <(curl -fsSL https://opam.ocaml.org/install.sh)'
fi

# 3. opam init + an OCaml 4.14.2 switch (the engine uses Stream, gone in 5.x) + dune.
if [ ! -d "$HOME/.opam" ]; then
  say "Initialising opam (first run)…"
  opam init -y --bare
fi
if ! opam switch list --short 2>/dev/null | grep -qx 4.14.2; then
  say "Creating OCaml 4.14.2 — this compiles the compiler and can take several minutes…"
  opam switch create 4.14.2
fi
opam switch set 4.14.2
eval "$(opam env --switch=4.14.2)"
say "Installing dune…"
opam install -y dune

# 4. Python 3 with tkinter.
command -v python3 >/dev/null 2>&1 || die "Python 3 not found — install it from https://www.python.org/downloads/"
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  warn "This Python has no tkinter (the GUI toolkit)."
  warn "Install Python from https://www.python.org/downloads/ (that build includes tkinter),"
  die  "then run this script again."
fi

# 5. Build the native engine (unless already built) and launch.
if [ ! -f resources/jape-engine ] || [ "${1:-}" = "--rebuild" ]; then
  say "Building the native Jape engine…"
  python3 build/make_dist.py --engine-only
else
  say "Native engine already built (pass --rebuild to recompile)."
fi
say "Launching PyJape…"
exec python3 run.py
