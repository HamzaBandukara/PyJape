# Building PyJape

This guide is for maintainers and contributors. If you only want to use
PyJape, download it from the Releases page (see the [README](../README.md)).

A PyJape build has two parts:

1. **The engine.** Jape's OCaml sources in `engine-src/` are compiled with dune
   into a native binary, `resources/jape-engine` (`jape-engine.exe` on
   Windows).
2. **The app.** PyInstaller bundles the Python/Tkinter app together with the
   whole `resources/` folder (engine and example logics) into a single folder
   that runs without anything else installed. A per-OS installer is then built
   from that folder.

`build/make_dist.py` does both steps.

## Platforms

Native code doesn't cross-compile, so each build has to run on its own OS:

| Target | Build on | Covers |
|---|---|---|
| **Windows x64** | a Windows PC (or CI) | almost all Windows PCs; Windows on ARM runs it under emulation |
| **macOS arm64** | an Apple Silicon Mac (or CI `macos-latest`) | every Mac since late 2020 (M1 and later) |
| **macOS x64** | an Intel Mac (or CI `macos-15-intel`) | Intel Macs; also runs on Apple Silicon under Rosetta |
| **Linux x64** | a Linux machine (or CI `ubuntu-22.04`) | most desktop Linux distributions |

If you can only ship one Mac build, ship x64, which runs everywhere (more
slowly under Rosetta). Ship arm64 as well for full speed on modern Macs.

## Easiest: build in the cloud (GitHub Actions)

The **Build distributables** workflow (`.github/workflows/build.yml`) builds
the engine and the app on Windows, both kinds of Mac, and Linux. Start it from
the Actions tab, or push a version tag:

```sh
git tag v1.0.0
git push origin v1.0.0
```

Every run uploads these as workflow artifacts:

- `PyJape-<os>-folder`: the one-folder app.
- `PyJape-<os>-installer`: `.exe` (Windows), `.dmg` (macOS) or `.tar.gz`
  (Linux).

When the run comes from a `v*` tag, it also creates a **draft GitHub Release**
with the installers attached. Check the draft, write the release notes, then
publish it. Workflow artifacts expire and are only visible to signed-in GitHub
users, so the Releases page is where users should download from.

> Before tagging, update the version in `build/installer/jape.iss`
> (`AppVersion`).

## Building locally

### Prerequisites

- **OCaml 4.14.x and dune.** It has to be 4.14: the engine uses `Stream`, which
  OCaml 5 removed.
  - macOS / Linux: `brew install opam` (or your distribution's opam), then
    `opam init -y`, `opam switch create 4.14.2`, `opam install -y dune`,
    `eval $(opam env)`
  - Windows: install opam 2.2 or later (`winget install OCaml.opam`), then
    `opam init`, `opam switch create 4.14.2`, `opam install dune`
- **Python 3.9+ with tkinter.** The python.org installers include it. On Linux:
  `sudo apt install python3-tk`.
- **PyInstaller:** `pip install pyinstaller`

### Build

```sh
python build/make_dist.py                 # build the engine, then package the app
python build/make_dist.py --engine-only   # build the engine only (enough for `python run.py`)
python build/make_dist.py --skip-engine   # reuse resources/jape-engine*, package only
```

The output goes in `build/dist/PyJape/`. On macOS you also get
`build/dist/PyJape.app`.

If `opam` is on your `PATH`, `make_dist.py` runs dune inside the opam
environment for you, so you don't have to activate the switch first.

### Make an installer

- **Windows:** install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then
  run `ISCC.exe build\installer\jape.iss`. The result is
  `build\installer\Output\PyJape-Setup.exe`.
- **macOS:** `hdiutil create -volname "PyJape" -srcfolder build/dist -ov -format UDZO PyJape.dmg`
- **Linux:** `tar -C build/dist -czf PyJape-linux-x64.tar.gz PyJape`

## Fast iteration (no OCaml needed after the first build)

Compiling the engine is the only slow or awkward step, and you rarely need to
repeat it. Once you have `resources/jape-engine[.exe]`:

1. **Working on the app:** run `python run.py`, edit the Python, run it again.
   You need only Python and tkinter.
2. **Testing the packaged app:** `python build/make_dist.py --skip-engine`
   runs only PyInstaller.
3. **Changing the engine:** `python build/make_dist.py` (needs OCaml and dune).

**Getting an engine without installing OCaml:** download the
`PyJape-<os>-folder` artifact from any Actions run, and copy
`_internal/resources/jape-engine[.exe]` out of it into `resources/`. It must
come from a build for the same OS. A Linux binary built under WSL, for example,
won't run in a Windows app.

## Run from source

To run PyJape straight from a checkout, without PyInstaller, build the engine
once and start the app with Python. It's the same native engine the installers
ship.

**One script per OS** does every step below and is safe to run again:

| OS | Command |
|---|---|
| **macOS** | double-click `scripts/setup-macos.command` (or `bash scripts/setup-macos.command`) |
| **Linux** | `bash scripts/setup-linux.sh` |
| **Windows** | `powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1` |

Each script installs the OCaml toolchain and Python/tkinter if they're missing,
compiles the engine and starts the app. On later runs it skips whatever is
already there. Pass `--rebuild` (`-Rebuild` on Windows) to force the engine to
be recompiled.

**By hand:**

1. Install OCaml 4.14 and dune (see [Prerequisites](#prerequisites)).
2. Install Python 3 with tkinter.
3. Build the engine, then run:

   ```sh
   python build/make_dist.py --engine-only   # builds resources/jape-engine[.exe]
   python run.py                              # finds the engine in resources/
   ```

After pulling new engine sources, run the first command again to rebuild the
engine.

## Code signing

Unsigned builds trigger a one-time warning on first launch. The README tells
users how to get past it:

- **macOS Gatekeeper.** To remove the warning, sign with an Apple Developer ID
  and notarize (`codesign` + `notarytool`). The bundle identifier is set in
  `build/jape.spec`.
- **Windows SmartScreen.** To remove the warning, sign the installer with an
  Authenticode certificate.

## How it fits together

- `make_dist.py` runs `dune build node_engine/engine_main.exe` in `engine-src/`
  and copies the result to `resources/jape-engine[.exe]`. (The `node_engine`
  directory has that name for historical reasons. It builds a native
  executable.) It then runs PyInstaller with `build/jape.spec`.
- When the app runs, `jape/engine.py: default_paths()` finds `resources/`,
  whether from a source checkout or a PyInstaller bundle, and starts the engine
  as a child process. The app and engine talk over stdin/stdout using Jape's
  GUI protocol, the same architecture as the original Java front-end.
- `tests/test_spacepath.py` checks that the app still works when it's installed
  under a path containing spaces, such as `C:\Program Files\PyJape`.

## Engine changes from upstream Jape

`engine-src/engine_src/` is Jape's `camlengine` with these differences:

- `moresys.ml` and `env.ml` no longer depend on OCaml's Unix library. As a
  result, external "oracle" provers can't be launched.
- `version.ml` is checked in. Upstream generates it from git.
- `dune` files were added. They replace upstream's Makefile.
- `main.ml`, `oracle.ml`, `lexparse.ml` and `sexpr.ml` are kept to match
  upstream, but they aren't compiled.
