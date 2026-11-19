#!/usr/bin/env bash
# PyJape — build the native engine from source and run it with Python (Linux).
#
# For anyone who wants to run PyJape from source. Installs the OCaml
# toolchain (once), compiles the native engine, and launches the app.
# Run:  bash scripts/setup-linux.sh     (or make it executable and ./scripts/setup-linux.sh)
#
# Safe to re-run. Pass --rebuild to force recompiling the engine.
set -euo pipefail

say()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
say "Working in: $(pwd)"

# 1. System prerequisites (C toolchain, opam build deps, python3 + tk).
if   command -v apt-get >/dev/null 2>&1; then PM=apt
elif command -v dnf     >/dev/null 2>&1; then PM=dnf
elif command -v pacman  >/dev/null 2>&1; then PM=pacman
else PM=; fi

case "$PM" in
  apt)    DEPS=(build-essential m4 unzip bubblewrap rsync git curl python3 python3-tk) ;;
  dnf)    DEPS=(gcc make m4 unzip bubblewrap rsync git curl python3 python3-tkinter) ;;
  pacman) DEPS=(base-devel m4 unzip bubblewrap rsync git curl python tk) ;;
esac
if [ -n "$PM" ]; then
  say "Installing build prerequisites with $PM (you may be asked for your password)…"
  case "$PM" in
    apt)    sudo apt-get update && sudo apt-get install -y "${DEPS[@]}" ;;
    dnf)    sudo dnf install -y "${DEPS[@]}" ;;
    pacman) sudo pacman -Sy --needed --noconfirm "${DEPS[@]}" ;;
  esac
else
  warn "Couldn't detect apt/dnf/pacman. Please install manually: a C compiler + make,"
  warn "curl, git, unzip, m4, bubblewrap, and Python 3 with tkinter."
fi

# 2. opam.
if ! command -v opam >/dev/null 2>&1; then
  say "Installing opam…"
  bash -c 'sh <(curl -fsSL https://opam.ocaml.org/install.sh)'
fi

# 3. opam init + OCaml 4.14.2 switch + dune.
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
command -v python3 >/dev/null 2>&1 || die "Python 3 not found — install it with your package manager."
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  die "Python has no tkinter. Install it (Debian/Ubuntu: sudo apt install python3-tk), then re-run."
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
