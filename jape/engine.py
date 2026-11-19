"""Bridge to the Jape proof engine, running as a child process.

The engine is a native binary (`resources/jape-engine[.exe]`, compiled from the
OCaml sources in `engine-src/`). It stays alive for the whole session and speaks
Jape's line-based GUI protocol on stdin/stdout, just as it did with the
original Java front-end. We answer its queries (font metrics, current
selection, dialogs) as they stream in, and send a user command only when it is
idle at its top-level GET prompt. The engine keeps all proof state itself.

This module is GUI-agnostic and synchronous, so it can be driven headlessly
(see tests/). The Tkinter app in app.py uses it from the main thread.
"""
import math
import os
import subprocess
import sys
import tempfile

from . import protocol

# Fallback font metrics for headless use; the GUI passes real ones so the
# engine lays out lines to exactly the height of the glyphs it draws.
FONT_SIZE = {0: 21, 1: 13, 2: 13}
def _default_font_info(fontnum):
    sz = FONT_SIZE.get(fontnum, FONT_SIZE[0])
    return (math.ceil(sz * 0.82), math.ceil(sz * 0.30), math.ceil(sz * 0.30))


def mono_measure(fontnum, text):
    """Default metric: monospace stub. The GUI passes a real measurer."""
    return len(text) * (10 if fontnum == 0 else 7)


class Engine:
    def __init__(self, engine_path, entry, measure=mono_measure, font_info=_default_font_info):
        """engine_path: the native engine binary. entry: the theory (.jt) to
        load at startup. measure/font_info: text metrics from the GUI."""
        self.engine_path = engine_path
        self.entry = entry
        self.measure = measure
        self.font_info = font_info        # fontnum -> (ascent, descent, leading)
        self.proc = None
        self.selection = []          # list of "x y cls" strings, answered on query
        self.disproof_selection = [] # list of "x y" strings: selected disproof-sequent formulas
        self.lines = []              # accumulated draw/menu/control lines (for parsing)
        self.booted = False
        self.on_alert = None         # optional callback(message)
        self.on_ask = None           # optional callback(message, buttons, default) -> button index
        self._ask_buttons = []       # labels from ASKSTART/ASKBUTTON, for the next ASKNOW
        self.alive = True
        self.save_path = None        # answered to WRITEFILENAME while saving

    # --- lifecycle --------------------------------------------------------
    def start(self):
        if not os.path.exists(self.engine_path):
            raise RuntimeError(
                "Could not find the Jape engine:\n  %s\n\n"
                "If you are running from source, build it first with\n"
                "  python build/make_dist.py --engine-only\n"
                "(see the README). If you installed PyJape, try reinstalling it."
                % self.engine_path)
        if os.name != 'nt' and not os.access(self.engine_path, os.X_OK):
            try:                           # PyInstaller can strip the exec bit
                os.chmod(self.engine_path, 0o755)
            except OSError:
                pass
        argv = [self.engine_path]
        # stderr -> temp file so it never blocks and we can read it if startup fails
        self._errfile = tempfile.TemporaryFile()
        try:
            self.proc = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._errfile,
                bufsize=0,
            )
        except OSError as e:
            raise RuntimeError("Could not run the engine binary:\n  %s\n\n%s"
                               % (self.engine_path, e))
        self.pump()                  # startup turn: first GET -> `use` -> idle
        if self.proc.poll() is not None or not self.booted:
            raise RuntimeError("The engine stopped during startup.\n\n" + self._startup_error())
        return self

    def _startup_error(self):
        try:
            self._errfile.seek(0)
            err = self._errfile.read().decode('utf-8', 'replace').strip()
        except Exception:
            err = ''
        return (err.splitlines()[-6:] and '\n'.join(err.splitlines()[-6:])) or \
            'The engine gave no error output.'

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.terminate()
            except Exception:
                pass

    # --- low-level io -----------------------------------------------------
    def _write(self, s):
        if not self.proc or self.proc.poll() is not None:
            self.alive = False
            raise RuntimeError('The engine is not running.')
        try:
            self.proc.stdin.write((s + '\n').encode('utf-8'))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self.alive = False
            raise RuntimeError('Lost the connection to the engine.')

    def _readline(self):
        raw = self.proc.stdout.readline()
        if raw == b'':
            self.alive = False
            return None
        return raw.decode('utf-8', 'replace').rstrip('\r\n')   # tolerate CRLF on Windows

    # --- query answering --------------------------------------------------
    def _metric_reply(self, f):
        head = f[0]
        fontnum = int(f[1]) if len(f) > 1 and f[1].lstrip('-').isdigit() else 0
        asc, desc, lead = self.font_info(fontnum)
        if head == 'STRINGSIZE':
            text = ' '.join(f[2:])
            return f"{int(round(self.measure(fontnum, text)))} {asc} {desc}"
        if head == 'FONTINFO':
            return f"{asc} {desc} {lead}"
        if head == 'POINTSIZE':
            return str(asc + desc)
        if head == 'PROCRUSTES':
            return f[2] if len(f) > 2 else ''
        return ''

    def _answer_query(self, line, head):
        """Answer a blocking query. Returns True if we handled it (a query)."""
        if head in ('FONTINFO', 'STRINGSIZE', 'POINTSIZE', 'PROCRUSTES'):
            self._write(self._metric_reply(protocol.japesplit(line))); return True
        if head == 'HOWTOTEXT' or head == 'READHIGHLIGHT' or head == 'MAKECHOICE':
            self._write('0'); return True
        if head == 'PANEGEOMETRY':
            self._write('0 0 800 600'); return True
        if head == 'FONTNAMES':
            self._write('\u0091'.join(['Courier'] * 6)); return True
        if head == 'ASKSTART':
            self._ask_buttons = []; return True
        if head == 'ASKBUTTON':
            self._ask_buttons.append(protocol.strip_controls(' '.join(protocol.japesplit(line)[1:])))
            return True
        if head == 'ASKNOW':
            f = protocol.japesplit(line)
            msg = protocol.strip_controls(' '.join(f[2:-1])) if len(f) > 3 else ''
            default = f[-1] if f and f[-1].isdigit() else '0'
            buttons, self._ask_buttons = self._ask_buttons, []
            if self.on_ask and len(buttons) > 1:
                # a real question (e.g. "wipe the worlds you have built?"): let the GUI ask
                try:
                    ans = int(self.on_ask(msg, buttons, int(default)))
                except Exception:
                    ans = int(default)
                self._write(str(ans if 0 <= ans < len(buttons) else int(default))); return True
            if msg and self.on_alert:
                self.on_alert(msg)
            self._write(default); return True
        if head == 'ASKDANGEROUSLY':
            f = protocol.japesplit(line)
            msg = protocol.strip_controls(' '.join(f[1:-2])) if len(f) > 3 else ''
            if msg and self.on_alert:
                self.on_alert(msg)
            self._write('0'); return True
        if head == 'WRITEFILENAME':
            self._write(self.save_path or ''); return True
        if head in ('multiLine', 'READFILENAME', 'ASKUNIFY', 'ASKLEMMA'):
            self._write(''); return True
        if head == 'GETPROOFSELECTIONS':
            for s in self.selection:
                self._write(s)
            self._write(''); return True
        if head == 'GETDISPROOFSELECTIONS':
            for s in self.disproof_selection:
                self._write(s)
            self._write(''); return True
        if head in ('GETPROOFTEXTSELECTIONS', 'GETGIVENTEXTSELECTIONS',
                    'GETDISPROOFTEXTSELECTIONS'):
            self._write(''); return True
        return False

    # --- the pump ---------------------------------------------------------
    def pump(self):
        """Read until the engine parks at its top-level GET (idle). On the very
        first GET, kick it off with `use`."""
        while True:
            line = self._readline()
            if line is None:
                return
            head = line.split(' ', 1)[0]
            if head == 'GET':
                if not self.booted:
                    self.booted = True
                    # quote + forward-slash the path: the install dir has spaces
                    # (e.g. C:\Program Files\PyJape) which would otherwise
                    # split the command and the theory would never load.
                    self._write('COMMAND use ' + self._enc_path(self.entry))
                    continue
                return
            if self._answer_query(line, head):
                continue
            self.lines.append(line)          # draw / menu / control line

    def command(self, cmd):
        """Send a user command and pump until idle again."""
        self._write(cmd)
        self.pump()

    def focus(self, num):
        """Switch the engine's focus to proof window `num`. The engine emits no
        redraw (it assumes the GUI cached the window), so we record a synthetic
        marker; the parser then routes any later draws for `num` to it."""
        self.command('COMMAND setfocus ' + str(num))
        self.lines.append('__FOCUS__ ' + str(num))

    def state(self, focus=None):
        return protocol.parse_transcript('\n'.join(self.lines), focus=focus)

    @staticmethod
    def _enc_path(path):
        # Quote (paths may have spaces) but KEEP the native separator. The command
        # tokenizer (uTF.words) preserves backslashes literally, and the engine's
        # Windows `isabsolute` test needs a backslash (index(':') < index('\\')) —
        # forward slashes make it treat an absolute path as relative to the theory
        # dir, so `use` fails with "Cannot read file: …\natural_deduction\C:\…".
        return '"' + path + '"'

    def save_proofs(self, path):
        """Save all current conjectures + proofs to `path` (a Jape .jp file),
        reusing the engine's own saveproofs. Returns True if the file exists."""
        self.save_path = self._enc_path(path)
        try:
            self.command('COMMAND saveproofs true')      # Save As -> WRITEFILENAME
        finally:
            self.save_path = None
        if os.path.exists(path):
            self._normalize_jp(path)
            return True
        return False

    @staticmethod
    def _normalize_jp(path):
        """Strip the UTF-8 BOM and convert CRLF->LF. The engine writes both on
        Windows (text-mode output), and the Windows engine's own `use` parser
        then fails to reload the file; a clean LF/no-BOM file loads everywhere."""
        try:
            with open(path, 'rb') as f:
                data = f.read()
            clean = data.lstrip(b'\xef\xbb\xbf').replace(b'\r\n', b'\n')
            if clean != data:
                with open(path, 'wb') as f:
                    f.write(clean)
        except OSError:
            pass

    def load_proofs(self, path):
        """Reload a saved .jp file (adds its conjectures/proofs)."""
        if os.path.exists(path):
            self._normalize_jp(path)         # fix BOM/CRLF from older saves so `use` can read it
            self.command('COMMAND use ' + self._enc_path(path))
            return True
        return False


ENGINE_NAME = 'jape-engine' + ('.exe' if os.name == 'nt' else '')


def default_paths():
    """Return (engine_path, theory_path): the native engine binary and the
    default theory (natural deduction, I2L.jt). Searches upwards for a
    `resources/` folder from the app's own location, so it works both from a
    source checkout and from a PyInstaller bundle. The JAPE_ENGINE and
    JAPE_ENTRY environment variables override the search."""
    env_engine, env_entry = os.environ.get('JAPE_ENGINE'), os.environ.get('JAPE_ENTRY')
    if env_engine:
        res = os.path.dirname(env_engine)
        return (env_engine, env_entry or os.path.join(res, 'examples', 'natural_deduction', 'I2L.jt'))
    marker = os.path.join('examples', 'natural_deduction', 'I2L.jt')
    bases = []
    if getattr(sys, 'frozen', False):                  # PyInstaller bundle
        bases.append(os.path.dirname(sys.executable))
        if getattr(sys, '_MEIPASS', None):
            bases.append(sys._MEIPASS)
    bases += [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
    for start in bases:
        d = start
        for _ in range(8):
            res = os.path.join(d, 'resources')
            if os.path.exists(os.path.join(res, marker)):
                return (os.path.join(res, ENGINE_NAME), env_entry or os.path.join(res, marker))
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    # Not found: return the expected source-checkout location, so the
    # "could not find the engine" error names a sensible path.
    here = os.path.dirname(os.path.abspath(__file__))
    res = os.path.normpath(os.path.join(here, '..', 'resources'))
    return (os.path.join(res, ENGINE_NAME), os.path.join(res, marker))
