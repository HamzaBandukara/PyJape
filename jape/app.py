"""PyJape: the Tkinter desktop front-end.

The Jape engine runs as a persistent child process (see engine.py); this module
draws its proofs and turns clicks and menu choices into engine commands. Engine
turns are fast, so we drive it synchronously on the main thread. Only the
one-off startup (loading the theory) is slow, and we run that just after the
window appears.
"""
import json
import os
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, filedialog

from . import engine as E
from . import protocol as P
from . import logic as L

# Student-saved work: their typed questions go in a "Saved" panel, persisted
# (with proofs) to a .jp file via the engine's own saveproofs.
SAVE_DIR = os.path.join(os.path.expanduser('~'), '.pyjape')
SAVE_FILE = os.path.join(SAVE_DIR, 'my_exercises.jp')
OLD_SAVE_DIR = os.path.join(os.path.expanduser('~'), '.jape_reloaded')   # pre-rename location
MINE = 'Saved'


def _migrate_save_dir():
    """The app used to save under ~/.jape_reloaded; it's now ~/.pyjape. If a
    student has the old folder and no new one yet, move it so their saved work
    carries over. Best-effort — never block startup on it."""
    try:
        if os.path.isdir(OLD_SAVE_DIR) and not os.path.exists(SAVE_DIR):
            os.rename(OLD_SAVE_DIR, SAVE_DIR)
    except OSError:
        pass

# ---- LaTeX-style input escapes: typing \and gives ∧, \forall gives ∀, … -------
ESCAPES = [
    ('implies', '→'), ('rightarrow', '→'), ('imp', '→'), ('to', '→'),
    ('wedge', '∧'), ('land', '∧'), ('and', '∧'),
    ('vee', '∨'), ('lor', '∨'), ('or', '∨'),
    ('lnot', '¬'), ('neg', '¬'), ('not', '¬'),
    ('turnstile', '⊢'), ('vdash', '⊢'), ('proves', '⊢'),
    ('bottom', '⊥'), ('false', '⊥'), ('bot', '⊥'), ('ff', '⊥'),
    ('true', '⊤'), ('top', '⊤'), ('tt', '⊤'),
    ('forall', '∀'), ('all', '∀'),
    ('exists', '∃'), ('some', '∃'), ('ex', '∃'),
]
_ESC_MAP = {k: v for k, v in ESCAPES}
_names = '|'.join(sorted((k for k, _ in ESCAPES), key=len, reverse=True))
_ESC_FULL = re.compile(r'\\(' + _names + r')', re.I)
_ESC_LIVE = re.compile(r'\\(' + _names + r')(?=[^A-Za-z])', re.I)
def _expand(s, rx):
    return rx.sub(lambda m: _ESC_MAP[m.group(1).lower()], s)

PAL = {
    'bg': '#ffffff', 'stage': '#eef1f7', 'ink': '#11162a', 'muted': '#697587',
    'amber': '#a8690a', 'line': '#dde3ee', 'line2': '#e9edf5', 'accent': '#2f5bd6',
    'red': '#d61f2b', 'selfill': '#fff0f0', 'ok': '#1a8a4a', 'okbg': '#e7f5ec', 'out': '#aab2c0',
    # Kripke countermodels: is a formula forced (true) at the selected world?
    'forced': '#1a8a4a', 'unforced': '#7a3fc4',
    'forcedbg': '#8fd3a8', 'unforcedbg': '#c9b3ef',     # world tints: must read clearly as green / violet
}

# Shown in the About dialog. The GPL (v2 §2(c)) asks that an interactive program
# display its copyright and no-warranty notice; the original Jape does this in a
# Java About box, so PyJape carries the same notice. The three legal paragraphs
# are kept word for word.
# ---- text size -------------------------------------------------------------
# Every font is a named tkfont.Font sized from ONE base, so zooming is a
# configure() per font and every widget using it follows live. Sizes are in
# points; the proof's fonts are measured for the engine, which re-lays out the
# proof when they change (see Engine.fonts_changed).
BASE_PT = 10
TEXT_SCALE = {
    'proof': 1.8,       # formulas in the proof (engine font 0)
    'reason': 1.1,      # line numbers, rule names (engine font 1)
    'reason_i': 1.1,    # provisos (engine font 2)
    'ui': 1.1,          # status line
    'term': 1.3,        # formulas outside the proof: entry, exercise list, tiles, labels
    'brand': 1.3,       # the "PyJape" wordmark
    'title': 1.6,       # About heading
    'body': 1.0,        # ordinary interface text and buttons
    'heading': 1.0,     # bold section headings
    'small': 0.9,       # hints and tags
    'small_bold': 0.9,
    'mono': 1.0,        # the \escape table
}
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.7, 2.5, 0.1
MAC_TEXT = 1.3          # Tk on a Mac counts 1pt = 1 logical px (72 dpi), elsewhere ~96 dpi
SETTINGS_FILE = os.path.join(SAVE_DIR, 'settings.json')


def _load_settings():
    try:
        with open(SETTINGS_FILE, encoding='utf-8') as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(d):
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        tmp = SETTINGS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, SETTINGS_FILE)
    except OSError:
        pass


def _enable_dpi_awareness():
    """Windows: ask to draw at the screen's real resolution. Otherwise, at
    125%/150% display scaling Windows stretches the window as a bitmap and all
    text is blurry. Must run before tk.Tk(); then `tk scaling` reports the real
    DPI and sizes in points come out right."""
    if os.name != 'nt':
        return
    try:
        import ctypes
    except ImportError:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)      # Windows 8.1+: system-DPI aware
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()            # Vista/7 fallback
    except Exception:
        pass


ABOUT_TEXT = """PyJape — a desktop front-end for the Jape proof calculator.
https://github.com/HamzaBandukara/PyJape

Jape engine and example logics copyright © 2003-19 Richard Bornat & Bernard Sufrin.
PyJape front-end copyright © 2026 Hamza Bandukara.

Jape is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

Jape is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License with PyJape (the LICENSE file). If not, see https://www.gnu.org/licenses/.

PyJape also includes Python, Tcl/Tk and the OCaml runtime; see THIRD_PARTY_NOTICES.md."""


class JapeApp:
    def __init__(self, root, engine_path, entry):
        self.root = root
        root.title('PyJape')
        self.aqua = root.tk.call('tk', 'windowingsystem') == 'aqua'
        # Screen pixels per layout pixel (layouts are designed at 96 dpi). With DPI
        # awareness, Windows/Linux report the real DPI in `tk scaling` (px per pt);
        # a Mac's Tk already works in logical pixels.
        self.dpi = 1.0 if self.aqua else max(1.0, float(root.tk.call('tk', 'scaling')) / (96 / 72))
        self.settings = _load_settings()
        try:
            z = float(self.settings.get('text_zoom', 1.0))
        except (TypeError, ValueError):
            z = 1.0
        self.zoom = round(min(ZOOM_MAX, max(ZOOM_MIN, z)), 2)
        self._init_w = min(self.px(1100), int(root.winfo_screenwidth() * 0.95))
        root.geometry('%dx%d' % (self._init_w, min(self.px(760), int(root.winfo_screenheight() * 0.9))))
        root.configure(bg=PAL['bg'])

        # Prefer a normal-metric serif that still carries the logic symbols
        # (NOT "Cambria Math" — its line metrics are huge, which spaces lines out).
        serif = self._pick_family(['Cambria', 'STIX Two Text', 'STIXGeneral',
                                   'DejaVu Serif', 'Georgia', 'Times New Roman', 'Times'])
        sans = self._pick_family(['Segoe UI', 'Helvetica', 'DejaVu Sans', 'Arial'])
        mono = self._pick_family(['Consolas', 'Menlo', 'DejaVu Sans Mono', 'Courier New', 'Courier'])
        fam = {'proof': serif, 'term': serif, 'mono': mono}
        style = {'reason_i': {'slant': 'italic'}, 'brand': {'weight': 'bold'}, 'title': {'weight': 'bold'},
                 'heading': {'weight': 'bold'}, 'small_bold': {'weight': 'bold'}}
        self.f = {k: tkfont.Font(family=fam.get(k, sans), **style.get(k, {})) for k in TEXT_SCALE}
        self.fonts = {0: self.f['proof'], 1: self.f['reason'], 2: self.f['reason_i']}   # the engine's fonts
        self.ui_font = self.f['ui']
        self.term_small = self.f['term']
        self._apply_text_size()

        self.eng = E.Engine(engine_path, entry, measure=self._measure, font_info=self._font_info)
        self.eng.font_names = self._engine_font_names
        self.eng.on_alert = self._alert
        self.eng.on_ask = self._ask
        self.state = P.State()
        self.selection = []          # [{x,y,cls}]
        self.item_pick = {}          # canvas item id -> {x,y,cls} (filled in _draw)
        self.active_panel = None
        self._cur_entries = []       # deduped entries shown in the exercise list
        self.cur_num = None          # window number of the one proof we keep open (single-window)
        self.show_table = tk.BooleanVar(value=True)   # "What we know" truth-table toggle
        self.force_big = False       # per-proof override to compute a >6-var table
        self._table_for = None       # proof the override currently applies to
        self.last_pane = 'proof'     # which pane Undo/Redo act on: 'proof' or 'disproof'
        self.d_open = set()          # proof windows whose countermodel pane the student opened
        self._auto_answer = None     # answer engine questions without asking (start again / close)
        self._quiet = False          # swallow engine alerts while doing that
        self.dsel = []               # selected disproof-sequent formulas ["x y"]
        self.d_pick = {}             # disproof canvas item id -> ('world', (x,y)) | ('seq', (x,y)) | ('unlabel', ((x,y), text))

        self._build_ui()
        root.protocol('WM_DELETE_WINDOW', self._on_close)   # auto-save on window close
        root.after(60, self._boot)

    def _multi_click_events(self):
        """Shift-, Ctrl- and (on a Mac) Cmd-click. NOT <Command-Button-1>
        elsewhere: on Windows Tk reports Num Lock as the same modifier (Mod1), so
        with Num Lock on every plain click would count as a Command-click."""
        evs = ['<Shift-Button-1>', '<Control-Button-1>']
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
            evs.append('<Command-Button-1>')
        return evs

    def _pick_family(self, prefs):
        avail = set(tkfont.families(self.root))
        for p in prefs:
            if p in avail:
                return p
        return prefs[-1]

    # ---- metrics (same fonts used for layout and drawing) ----------------
    def _measure(self, fontnum, text):
        return self.fonts.get(fontnum, self.fonts[0]).measure(text)

    def _font_info(self, fontnum):
        """Real metrics of the font we actually draw with, so the engine spaces
        lines to match the glyphs (a small leading keeps lines from touching)."""
        f = self.fonts.get(fontnum, self.fonts[0])
        return (f.metrics('ascent'), f.metrics('descent'), max(2, self.zpx(2)))

    def _engine_font_names(self):
        """Names for the engine's fonts that change with their size, so its
        width caches never mix up two fonts or two sizes."""
        names = ['%s-%s-%d' % (self.fonts[i].actual('family'), self.fonts[i].actual('size'), i)
                 for i in range(3)]
        return [n.replace(' ', '_') for n in names] + ['PyJapeFont%d' % i for i in range(3, 6)]

    # ---- text size -------------------------------------------------------
    def px(self, n):
        """A layout length in screen pixels (follows the display's DPI)."""
        return int(round(n * self.dpi))

    def zpx(self, n):
        """A length that should grow with the text, like a wrap width."""
        return int(round(n * self.dpi * self.zoom))

    def _apply_text_size(self):
        k = self.zoom * (MAC_TEXT if self.aqua else 1.0)
        for name, font in self.f.items():
            font.configure(size=max(6, round(BASE_PT * TEXT_SCALE[name] * k)))
        # widgets without an explicit font (toolbar buttons, menus) follow too
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
            try:
                tkfont.nametofont(name, root=self.root).configure(size=max(6, round(BASE_PT * k)))
            except tk.TclError:
                pass

    def _key(self, k):
        return ('Cmd+' if self.aqua else 'Ctrl+') + k

    def set_zoom(self, z):
        z = round(min(ZOOM_MAX, max(ZOOM_MIN, z)), 2)
        if z != self.zoom:
            self.zoom = z
            self._apply_text_size()
            self.side.configure(width=self._side_width())
            try:
                self.eng.fonts_changed(self.cur_num)     # the engine re-lays out the proof
            except Exception as e:
                self._set_status(str(e), 'error'); return
            self.refresh()
            self.settings['text_zoom'] = z
            _save_settings(self.settings)
        self._set_status('Text size %d%%   (%s bigger, %s smaller, %s normal)'
                         % (round(z * 100), self._key('='), self._key('−'), self._key('0')))

    def zoom_by(self, steps):
        self.set_zoom(round(self.zoom / ZOOM_STEP + steps) * ZOOM_STEP)

    def _bind_keys(self):
        """Undo/redo and text size. Ctrl everywhere; Cmd as well on a Mac only:
        on Windows, Tk reports Num Lock as the same modifier as Command (Mod1),
        so a <Command-…> binding there fires on the plain key with Num Lock on."""
        mods = ['Control'] + (['Command'] if self.aqua else [])
        acts = [(('z',), self.undo), (('Z',), self.redo),
                (('equal', 'plus', 'KP_Add'), lambda: self.zoom_by(+1)),
                (('minus', 'underscore', 'KP_Subtract'), lambda: self.zoom_by(-1)),
                (('0', 'KP_0', 'KP_Insert'), lambda: self.set_zoom(1.0))]
        for m in mods:
            for keys, fn in acts:
                for k in keys:
                    # <Control-Key-0>, not <Control-0>: a bare digit means a mouse button
                    self.root.bind_all('<%s-Key-%s>' % (m, k), lambda e, fn=fn: (fn(), 'break')[1])

    def _side_width(self):
        win = self.root.winfo_width()
        win = win if win > 1 else self._init_w
        return max(self.px(300), min(self.zpx(360), int(win * 0.45)))

    def _wrap(self):
        """Wrap width for text in the sidebar."""
        return self._side_width() - self.px(30)

    # ---- layout ----------------------------------------------------------
    def _build_ui(self):
        self.menubar = tk.Frame(self.root, bg=PAL['bg'])
        self.menubar.pack(side='top', fill='x')
        tk.Label(self.menubar, text='PyJape', font=self.f['brand'],
                 bg=PAL['bg'], fg=PAL['ink']).pack(side='left', padx=(10, 4), pady=6)
        self.title_lbl = tk.Label(self.menubar, text='', font=self.term_small, bg=PAL['bg'], fg=PAL['muted'])
        self.title_lbl.pack(side='right', padx=10)
        self.menu_holder = tk.Frame(self.menubar, bg=PAL['bg'])
        self.menu_holder.pack(side='left')
        view = tk.Menubutton(self.menubar, text='View', relief='flat', bg=PAL['bg'], fg=PAL['ink'])
        vm = tk.Menu(view, tearoff=0)
        vm.add_command(label='Bigger text', accelerator=self._key('='), command=lambda: self.zoom_by(+1))
        vm.add_command(label='Smaller text', accelerator=self._key('−'), command=lambda: self.zoom_by(-1))
        vm.add_command(label='Normal text size', accelerator=self._key('0'), command=lambda: self.set_zoom(1.0))
        view.configure(menu=vm)
        view.pack(side='left', padx=2)
        tk.Button(self.menubar, text='↩ Undo', command=self.undo, relief='flat',
                  bg=PAL['bg'], fg=PAL['ink'], highlightbackground=PAL['bg']).pack(side='left', padx=6)
        tk.Button(self.menubar, text='↺ Restart proof', command=self.restart_proof, relief='flat',
                  bg=PAL['bg'], fg=PAL['ink'], highlightbackground=PAL['bg']).pack(side='left', padx=2)
        tk.Button(self.menubar, text='⊭ Find countermodel (experimental)', command=self.disprove, relief='flat',
                  bg=PAL['bg'], fg=PAL['ink'], highlightbackground=PAL['bg']).pack(side='left', padx=2)
        for txt, fn in (('Save', self.save_work), ('Save as…', self.save_as), ('Open…', self.open_file)):
            tk.Button(self.menubar, text=txt, command=fn, relief='flat',
                      bg=PAL['bg'], fg=PAL['ink'], highlightbackground=PAL['bg']).pack(side='left', padx=2)
        tk.Button(self.menubar, text='About', command=self._about, relief='flat',
                  bg=PAL['bg'], fg=PAL['muted'], highlightbackground=PAL['bg']).pack(side='left', padx=2)

        body = tk.Frame(self.root, bg=PAL['bg'])
        body.pack(side='top', fill='both', expand=True)

        # proof canvas (scrollable)
        stage = tk.Frame(body, bg=PAL['stage'])
        stage.pack(side='left', fill='both', expand=True)

        # Status bar sits directly above the proof, where the student is looking,
        # so rule feedback ("✗ that rule doesn't apply", "✓ complete") is seen.
        statusbar = tk.Frame(stage, bg=PAL['bg'])
        statusbar.pack(side='top', fill='x')
        self.status = tk.Label(statusbar, text='starting…', anchor='w',
                               bg=PAL['bg'], fg=PAL['muted'], font=self.f['ui'])
        self.status.pack(fill='x', padx=16, pady=(8, 6))
        tk.Frame(stage, bg=PAL['line'], height=1).pack(side='top', fill='x')

        # The proof, and (only while a disproof is open) the Kripke countermodel
        # under it, share the stage in a vertical split below the status strip.
        self.split = tk.PanedWindow(stage, orient='vertical', bg=PAL['line'], bd=0,
                                    sashwidth=self.px(6), sashrelief='flat', showhandle=False)
        self.split.pack(side='top', fill='both', expand=True)
        proof_frame = tk.Frame(self.split, bg=PAL['bg'])
        self.split.add(proof_frame, stretch='always', minsize=self.px(120))
        self.canvas = tk.Canvas(proof_frame, bg=PAL['bg'], highlightthickness=0)
        vs = tk.Scrollbar(proof_frame, orient='vertical', command=self.canvas.yview)
        hs = tk.Scrollbar(proof_frame, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side='right', fill='y'); hs.pack(side='bottom', fill='x')
        self.canvas.pack(side='left', fill='both', expand=True, padx=16, pady=16)
        self._build_disproof_ui()
        self.canvas.bind('<Button-1>', lambda e: self._on_click(e, False))
        # multi-select: Shift-click, and Ctrl-click / Cmd-click (students use these)
        for seq in self._multi_click_events():
            self.canvas.bind(seq, lambda e: self._on_click(e, False, multi=True))

        # sidebar
        side = self.side = tk.Frame(body, bg=PAL['bg'], width=self._side_width())
        side.pack(side='right', fill='y'); side.pack_propagate(False)
        tk.Label(side, text='NEW EXERCISE', font=self.f['heading'],
                 bg=PAL['bg'], fg=PAL['muted']).pack(anchor='w', padx=14, pady=(14, 4))
        row = tk.Frame(side, bg=PAL['bg']); row.pack(fill='x', padx=14)
        self.newvar = tk.StringVar()
        self.newentry = tk.Entry(row, textvariable=self.newvar, font=self.term_small,
                                 bg='white', fg=PAL['ink'], insertbackground=PAL['ink'],
                                 disabledbackground='white', readonlybackground='white',
                                 relief='solid', bd=1, highlightthickness=0)
        self.newentry.pack(side='left', fill='x', expand=True)
        self.newentry.bind('<Return>', lambda e: self.new_exercise())
        self.newvar.trace_add('write', self._live_escape)
        tk.Button(row, text='Prove', command=self.new_exercise, bg=PAL['accent'], fg='white',
                  relief='flat', highlightbackground=PAL['accent']).pack(side='left', padx=(6, 0))
        tk.Label(side, text='Type an operator, or its escape (case-insensitive):',
                 font=self.f['body'], bg=PAL['bg'], fg=PAL['muted']).pack(anchor='w', padx=14, pady=(6, 2))
        ops = [('→', '\\imp'), ('∧', '\\and'), ('∨', '\\or'), ('¬', '\\not'), ('⊢', '\\vdash'),
               ('⊥', '\\bot'), ('⊤', '\\top'), ('∀', '\\forall'), ('∃', '\\exists')]
        optbl = tk.Frame(side, bg=PAL['bg']); optbl.pack(anchor='w', padx=14, pady=(0, 8))
        for i, (sym, esc) in enumerate(ops):
            r, cbase = divmod(i, 3)
            tk.Label(optbl, text=sym, font=self.term_small, bg=PAL['bg'], fg=PAL['ink']
                     ).grid(row=r, column=cbase * 2, sticky='e', padx=(0, 3), pady=1)
            tk.Label(optbl, text=esc, font=self.f['mono'], bg=PAL['bg'], fg=PAL['muted']
                     ).grid(row=r, column=cbase * 2 + 1, sticky='w', padx=(0, 14))

        self.known_lbl = tk.Label(side, text='WHAT WE KNOW', font=self.f['heading'],
                                  bg=PAL['bg'], fg=PAL['muted'])
        self.known = tk.Frame(side, bg=PAL['bg'])

        self.ex_label = tk.Label(side, text='EXERCISES', font=self.f['heading'],
                                 bg=PAL['bg'], fg=PAL['muted'])
        self.ex_label.pack(anchor='w', padx=14, pady=(10, 4))
        self.tabs = tk.Frame(side, bg=PAL['bg']); self.tabs.pack(fill='x', padx=14)
        lb = tk.Frame(side, bg=PAL['bg']); lb.pack(fill='both', expand=True, padx=14, pady=(4, 10))
        self.exlist = tk.Listbox(lb, font=self.term_small, activestyle='none',
                                 bg='white', fg=PAL['ink'], selectbackground=PAL['accent'],
                                 selectforeground='white', highlightthickness=1,
                                 highlightbackground=PAL['line'], bd=0)
        esc = tk.Scrollbar(lb, orient='vertical', command=self.exlist.yview)
        self.exlist.configure(yscrollcommand=esc.set)
        esc.pack(side='right', fill='y'); self.exlist.pack(side='left', fill='both', expand=True)
        self.exlist.bind('<Double-Button-1>', self._on_exercise)

        self._bind_keys()          # Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z redo, Ctrl/Cmd +/−/0 text size

    def _about(self):
        """A small read-only About window carrying Jape's GPL copyright and
        no-warranty notice (GPL v2 §2(c)), as the original Jape does."""
        win = tk.Toplevel(self.root)
        win.title('About PyJape')
        win.configure(bg=PAL['bg'])
        win.transient(self.root)
        win.resizable(False, False)
        tk.Label(win, text='PyJape', font=self.f['title'],
                 bg=PAL['bg'], fg=PAL['ink']).pack(anchor='w', padx=18, pady=(16, 2))
        txt = tk.Text(win, width=64, height=20, wrap='word', relief='flat',
                      bg=PAL['bg'], fg=PAL['ink'], font=self.f['body'],
                      padx=18, pady=4, cursor='arrow', highlightthickness=0)
        txt.insert('1.0', ABOUT_TEXT)
        txt.configure(state='disabled')          # read-only
        txt.pack(fill='both', expand=True)
        tk.Button(win, text='Close', command=win.destroy, relief='flat',
                  bg=PAL['bg'], fg=PAL['ink'], highlightbackground=PAL['bg']
                  ).pack(anchor='e', padx=18, pady=(4, 14))
        win.bind('<Escape>', lambda e: win.destroy())
        win.update_idletasks()
        # centre over the main window
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 3
        win.geometry('+%d+%d' % (max(x, 0), max(y, 0)))
        win.focus_set()

    # ---- engine driving --------------------------------------------------
    def _boot(self):
        _migrate_save_dir()          # carry over work saved under the old name
        self._set_status('loading engine…')
        self.root.update_idletasks()
        try:
            self.eng.start()
        except Exception as e:
            self._set_status('Engine failed to start — see the dialog.')
            messagebox.showerror('PyJape — could not start the engine', str(e))
            return
        note = None
        if os.path.exists(SAVE_FILE):                 # restore saved questions + proofs
            try:
                self._load_saved(SAVE_FILE)
                n = len(self.eng.state().panels.get(MINE, []))
                note = ('Restored %d saved exercise(s).' % n) if n else None
            except Exception as e:
                messagebox.showwarning('PyJape — could not load your saved work',
                                       'Saved file:\n  %s\n\n%s' % (SAVE_FILE, e))
                note = 'Could not load saved work.'
        self.refresh()
        if note:
            self._set_status(note)

    def save_work(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            ok = self.eng.save_proofs(SAVE_FILE)
            self._set_status('Saved to ' + SAVE_FILE if ok else 'Nothing to save yet.')
        except Exception as e:
            self._set_status('Save failed: %s' % e)
        self.refresh()

    _FT = [('Jape proof files', '*.jp'), ('All files', '*.*')]

    def save_as(self):
        path = filedialog.asksaveasfilename(title='Save proofs as',
                                            defaultextension='.jp', filetypes=self._FT)
        if not path:
            return
        try:
            ok = self.eng.save_proofs(path)
            self._set_status('Saved to ' + path if ok else 'Nothing to save yet.')
        except Exception as e:
            self._set_status('Save failed: %s' % e)
        self.refresh()

    def open_file(self):
        path = filedialog.askopenfilename(title='Open a saved proof file', filetypes=self._FT)
        if not path:
            return
        try:
            self._load_saved(path)
            n = len(self.eng.state().panels.get(MINE, []))
            self._set_status('Opened %s — %d saved exercise(s).' % (os.path.basename(path), n))
        except Exception as e:
            self._set_status('Open failed: %s' % e)
        self.refresh()

    def _saved_names_in_file(self, path):
        """Read the names of the student's own (MINE panel) conjectures straight
        from the .jp, so we can show them even if the engine's `use` doesn't
        re-emit the panel (observed on the Windows engine)."""
        names, cur = [], None
        try:
            with open(path, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    s = line.strip().lstrip('﻿')
                    if s.startswith('CONJECTUREPANEL'):
                        cur = s[len('CONJECTUREPANEL'):].strip().strip('"')
                    elif s.startswith('CURRENTPROOF') and cur == MINE:
                        q = s[len('CURRENTPROOF'):].strip()
                        if len(q) >= 2 and q[0] == '"' and q[-1] == '"':
                            names.append(q[1:-1])
        except Exception:
            pass
        return names

    def _load_saved(self, path):
        """Robust reload: register the student's conjectures (reliably shows them
        in the Saved tab), then `use` the file to load their proofs."""
        for name in self._saved_names_in_file(path):
            try:
                self.eng.command('COMMAND addnewconjecture ' + MINE + ' ' + name)
            except Exception:
                break
        self.eng.load_proofs(path)

    def _on_close(self):
        # auto-save the workbook so nothing is lost between sessions
        try:
            if getattr(self.eng, 'alive', False):
                os.makedirs(SAVE_DIR, exist_ok=True)
                self.eng.save_proofs(SAVE_FILE)
        except Exception:
            pass
        try:
            self.eng.stop()
        except Exception:
            pass
        self.root.destroy()

    def _alert(self, msg):
        if not self._quiet:
            self._set_status(msg, 'warn')

    def _ask(self, msg, buttons, default):
        """A real question from the engine (e.g. "wipe the worlds you have
        built?"). Two buttons map onto OK/Cancel; the first is the action."""
        if self._auto_answer is not None:
            return self._auto_answer
        if len(buttons) == 2:
            yes = messagebox.askokcancel('PyJape', msg + '\n\n(OK = %s)' % buttons[0],
                                         default=('ok' if default == 0 else 'cancel'))
            return 0 if yes else 1
        return default

    def _proof_sig(self):
        """A cheap fingerprint of the current proof drawing. If a rule leaves it
        unchanged, the move had no effect (the engine silently declined it)."""
        st = self.state
        return (st.proof_title, tuple((t['x'], t['y'], t['cls'], t['text']) for t in st.texts))

    def command(self, cmd, use_selection=False, is_rule=False):
        if not self.eng.alive:
            self._set_status('The engine is not running — restart the app.', 'error'); return
        if use_selection:
            self.eng.selection = [f"{s['x']} {s['y']} {s['cls']}" for s in self.selection]
        before = self._proof_sig()
        had_selection = bool(self.selection)
        self._set_status('working…')
        self.root.update_idletasks()
        try:
            self.eng.command(cmd)
        except Exception as e:
            self._set_status(str(e), 'error'); return
        self.eng.selection = []
        self.selection = []
        self.refresh()
        # If a rule changed nothing and the engine said nothing, it didn't apply —
        # tell the student so they don't keep re-clicking thinking they misclicked.
        if is_rule and not self.state.alert and self._proof_sig() == before:
            if not had_selection:
                self._set_status('✗ Select a formula first (click the conclusion, or a '
                                 'hypothesis), then choose the rule.', 'error')
            else:
                self._set_status('✗ That rule doesn’t apply to the selected formula here — '
                                 'try a different rule or selection.', 'error')

    def undo(self):
        self.command('COMMAND undo_disproof' if self._in_disproof() else 'COMMAND undo_proof')

    def redo(self):
        self.command('COMMAND redo_disproof' if self._in_disproof() else 'COMMAND redo_proof')

    def _in_disproof(self):
        return self.last_pane == 'disproof' and self.state.disproof is not None

    def restart_proof(self):
        """Discard the proof tree and go back to the bare goal, so a student can
        retry a proof — including a completed one, and one just loaded from a
        file. We prune the root conclusion rather than undo step-by-step: undo
        replays the engine's edit history, which a freshly-loaded proof doesn't
        have (loading installs the finished tree in one go), so undo/backtrack
        silently do nothing on it. Pruning the root works on the proof tree
        directly, so it resets a loaded proof too."""
        if not self.eng.alive or not self.state.proof_title:
            return
        concl = [t for t in self.state.texts if t['font'] == 0 and t['cls'] == 1]
        if not concl:
            return
        root = max(concl, key=lambda t: t['y'])        # the overall goal: bottom line
        self._set_status('restarting…'); self.root.update_idletasks()
        try:
            self.eng.selection = ['%d %d 1' % (root['x'], root['y'])]
            self.eng.command('COMMAND prune')
        except Exception as e:
            self.eng.selection = []
            self._set_status(str(e), 'error'); return
        self.eng.selection = []
        self.selection = []
        self.refresh()
        self._set_status('proof restarted')

    def new_exercise(self):
        if not self.eng.alive:
            self._set_status('The engine is not running — restart the app.'); return
        text = _expand(self.newvar.get(), _ESC_FULL).strip()
        if not text:
            return
        self._set_status('working…'); self.root.update_idletasks()
        try:
            self.eng.command('COMMAND addnewconjecture ' + MINE + ' ' + text)   # student's own panel
            st = self.eng.state()
            cmd = P.conjecture_command(st, st.selected['panel'], st.selected['name']) if st.selected else None
            if cmd:
                self._open_or_focus(st.selected['name'], cmd)
            else:
                self._set_status('could not parse “%s”' % text); return
        except Exception as e:
            self._set_status(str(e)); return
        self.selection = []
        self.refresh()

    # Jape is multi-window; we show one proof at a time. If the chosen conjecture
    # already has an open proof window, switch focus to it (keeps all progress);
    # otherwise start a new proof. `display` is the proof/conjecture name as it
    # appears in OPENPROOF (same text the panel shows).
    def _open_or_focus(self, display, cmd):
        wins = P.open_windows(self.eng.lines)
        if display in wins:
            self.eng.focus(wins[display])
            self.cur_num = wins[display]
        else:
            self.eng.command('COMMAND proveconjecture ' + cmd)
            self.cur_num = self.eng.state().latest

    # ---- rendering -------------------------------------------------------
    def refresh(self):
        self.state = self.eng.state(focus=self.cur_num)
        self.cur_num = self.state.focus            # follow if the focused window closed
        # The engine can't drop a countermodel, only reset it to one blank world.
        # Treat a blank one as "no countermodel" unless the student opened the pane
        # (so Close, and a reloaded file with a closed model, keep the pane hidden).
        if P.is_blank(self.state.disproof) and self.cur_num not in self.d_open:
            self.state.disproof = None
        self._draw()
        self._draw_disproof()
        self._rebuild_menus()
        self._rebuild_panels()
        self._known_panel()
        st = self.state
        if st.alert:
            self._set_status(st.alert, 'warn')
        elif st.disproof is not None and P.is_countermodel(st.disproof):
            self._set_status('✓ countermodel found for ' + st.proof_title + ' — press Done to record it', 'ok')
        elif st.proof_title and L.is_complete(st.texts):
            self._set_status('✓ complete — ' + st.proof_title, 'ok')
        else:
            self._set_status('proving ' + st.proof_title if st.proof_title else 'ready')
        self.title_lbl.config(text=st.proof_title or '')

    def _draw(self):
        c = self.canvas
        c.delete('all')
        texts, lines, rects = self.state.texts, self.state.lines, self.state.rects
        self.item_pick = {}                      # canvas item id -> {x,y,cls}
        if not texts and not lines:
            c.create_text(self.px(24), self.px(80), anchor='w', fill=PAL['muted'], font=self.ui_font,
                          text='No proof open — type a conjecture, or pick one →')
            c.configure(scrollregion=(0, 0, self.zpx(520), self.zpx(180)))
            return
        xs = [t['x'] for t in texts] + [l['x1'] for l in lines] + [l['x2'] for l in lines] + [r['x'] for r in rects]
        ys = [t['y'] for t in texts] + [l['y1'] for l in lines] + [l['y2'] for l in lines] + [r['y'] for r in rects]
        pad = self.px(24)
        ox = -min(xs) + pad
        oy = -min(ys) + pad + self.px(20)
        for l in lines:
            c.create_line(l['x1'] + ox, l['y1'] + oy, l['x2'] + ox, l['y2'] + oy, fill=PAL['ink'])
        for r in rects:
            c.create_rectangle(r['x'] + ox, r['y'] + oy, r['x'] + r['w'] + ox, r['y'] + r['h'] + oy,
                               outline=PAL['line'])
        for t in texts:
            fnt = self.fonts.get(t['font'], self.fonts[0])
            asc = fnt.metrics('ascent')
            sx = t['x'] + ox
            baseline = t['y'] + oy
            w = fnt.measure(t['text'])
            if t['font'] == 0 and self._sel_contains(t):
                self._draw_selmark(sx, baseline, w, fnt, t['cls'])
            color = PAL['amber'] if t['font'] == 2 else (PAL['muted'] if t['font'] == 1 else PAL['ink'])
            item = c.create_text(sx, baseline - asc, text=t['text'], anchor='nw', font=fnt, fill=color)
            if t['font'] == 0:                    # only formulas are selectable
                self.item_pick[item] = {'x': t['x'], 'y': t['y'], 'cls': t['cls']}
        # With several goals open and nothing selected, mark the one the "What we
        # know" panel is describing (a selection already shows its own red mark).
        if not self.selection:
            gtext, _, gtot = L.active_case(texts, rects, self.selection)
            if gtot > 1:
                g = L.open_goals(texts)[0]
                fnt = self.fonts[0]
                by = g['y'] + oy
                bx = g['x'] + ox - 9
                c.create_rectangle(bx, by - fnt.metrics('ascent') + 1, bx + 3, by + fnt.metrics('descent') - 1,
                                   fill=PAL['accent'], outline='')
        bbox = c.bbox('all')
        if bbox:
            c.configure(scrollregion=(0, 0, bbox[2] + pad, bbox[3] + pad))

    def _draw_selmark(self, sx, baseline, w, fnt, cls):
        # Jape convention: a HYPOTHESIS is a downward selection — bracket open at
        # the bottom (⊓, above the formula); a CONCLUSION is an upward selection —
        # bracket open at the top (⊔, below the formula).
        asc = fnt.metrics('ascent'); desc = fnt.metrics('descent')
        x0, x1, tick = sx - 4, sx + w + 4, 6
        c = self.canvas
        if cls == 2:                                   # hypothesis: ⊓ above, opens downward
            y = baseline - asc - 2
            c.create_line(x0, y + tick, x0, y, x1, y, x1, y + tick, fill=PAL['red'], width=2)
        else:                                          # conclusion: ⊔ below, opens upward
            y = baseline + desc + 2
            c.create_line(x0, y - tick, x0, y, x1, y, x1, y - tick, fill=PAL['red'], width=2)

    def _sel_contains(self, t):
        return any(s['x'] == t['x'] and s['y'] == t['y'] for s in self.selection)

    # ---- interaction -----------------------------------------------------
    def _on_click(self, ev, dbl, multi=False):
        # Use the canvas's own item geometry (not hand-computed boxes) so clicks
        # land exactly on what's drawn, regardless of font metrics / DPI scaling.
        self.last_pane = 'proof'                  # Undo now means the proof
        x = self.canvas.canvasx(ev.x); y = self.canvas.canvasy(ev.y)
        picked = None
        for it in reversed(self.canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2)):
            if it in self.item_pick:
                picked = dict(self.item_pick[it]); break
        if picked is None:                        # also try the nearest item within a few px
            near = self.canvas.find_closest(x, y)
            if near and near[0] in self.item_pick:
                bx = self.canvas.bbox(near[0])
                if bx and bx[0] - 6 <= x <= bx[2] + 6 and bx[1] - 4 <= y <= bx[3] + 4:
                    picked = dict(self.item_pick[near[0]])
        if picked is None:
            self.selection = []; self._draw(); self._known_panel(); return
        if multi:
            i = next((k for k, s in enumerate(self.selection)
                      if s['x'] == picked['x'] and s['y'] == picked['y']), -1)
            if i >= 0:
                self.selection.pop(i)
            else:
                self.selection.append(picked)
        else:
            self.selection = [picked]
        self._draw()
        self._known_panel()      # scope follows the selected line

    def _on_exercise(self, ev):
        # use the row under the cursor (robust: curselection() can be empty at
        # the moment a double-click fires)
        idx = self.exlist.nearest(ev.y)
        if not (0 <= idx < len(self._cur_entries)):
            return
        if not self.eng.alive:
            self._set_status('The engine is not running — restart the app.'); return
        e = self._cur_entries[idx]
        self._set_status('opening ' + e['display'] + ' …'); self.root.update_idletasks()
        try:
            self._open_or_focus(e['display'], e['command'])
        except Exception as ex:
            self._set_status(str(ex)); return
        self.selection = []
        self.refresh()

    # ---- the Kripke countermodel ("disproof") pane -------------------------
    # The engine owns the model; we draw what it sends and turn clicks into its
    # disproof commands. World coordinates are the engine's own (they identify
    # the world); its y axis points up, so a child world (greater y) is drawn
    # ABOVE its parent. Interaction is click-based: click a world to select it,
    # click a tile to put that formula on it, Shift-click a higher world to
    # link/unlink it, click × to take a label off, click a formula in the
    # sequent to colour the worlds by whether it holds there.
    WORLD_R = 13
    WORLD_DX, WORLD_DY = 150, 100     # spacing for worlds we add

    def _build_disproof_ui(self):
        self._dshown = False
        f = self.dframe = tk.Frame(self.split, bg=PAL['bg'])
        head = tk.Frame(f, bg=PAL['bg']); head.pack(side='top', fill='x', padx=16, pady=(8, 2))
        tk.Label(head, text='COUNTERMODEL', font=self.f['heading'],
                 bg=PAL['bg'], fg=PAL['muted']).pack(side='left')
        tk.Label(head, text='EXPERIMENTAL', font=self.f['small_bold'],
                 bg=PAL['amber'], fg='white', padx=4).pack(side='left', padx=(6, 0))
        for txt, fn in (('✕ Close', self.close_disproof), ('Done', self.disproof_done),
                        ('Start again', self.restart_disproof), ('Delete world', self.delete_world),
                        ('+ World above', self.add_world)):
            tk.Button(head, text=txt, command=fn, relief='flat', font=self.f['body'],
                      bg=PAL['bg'], fg=PAL['accent'], highlightbackground=PAL['bg']
                      ).pack(side='right', padx=2)
        f.bind('<Configure>', lambda e: self.dmsg.configure(wraplength=max(self.px(200), e.width - self.px(40))))
        self.dmsg = tk.Label(f, text='', anchor='w', justify='left', wraplength=self.px(640),
                             bg=PAL['bg'], fg=PAL['muted'], font=self.f['body'])
        self.dmsg.pack(side='top', fill='x', padx=16)

        bar = tk.Frame(f, bg=PAL['bg']); bar.pack(side='bottom', fill='x', padx=16, pady=(2, 8))
        tk.Label(bar, text='Put on the selected world:', font=self.f['body'],
                 bg=PAL['bg'], fg=PAL['muted']).pack(side='left', padx=(0, 6))
        self.tilebar = tk.Frame(bar, bg=PAL['bg']); self.tilebar.pack(side='left')
        self.labelvar = tk.StringVar()
        ent = tk.Entry(bar, textvariable=self.labelvar, font=self.term_small, width=12,
                       bg='white', fg=PAL['ink'], relief='solid', bd=1, highlightthickness=0)
        ent.pack(side='left', padx=(10, 4))
        ent.bind('<Return>', lambda e: self.add_custom_label())
        tk.Button(bar, text='Add', command=self.add_custom_label, relief='flat', font=self.f['body'],
                  bg=PAL['bg'], fg=PAL['accent'], highlightbackground=PAL['bg']).pack(side='left')
        tk.Label(bar, text='e.g. Q, R(i,j), actual j', font=self.f['small'],
                 bg=PAL['bg'], fg=PAL['muted']).pack(side='left', padx=6)

        box = tk.Frame(f, bg=PAL['bg']); box.pack(side='top', fill='both', expand=True)
        self.dcanvas = tk.Canvas(box, bg=PAL['bg'], highlightthickness=0)
        vs = tk.Scrollbar(box, orient='vertical', command=self.dcanvas.yview)
        hs = tk.Scrollbar(box, orient='horizontal', command=self.dcanvas.xview)
        self.dcanvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side='right', fill='y'); hs.pack(side='bottom', fill='x')
        self.dcanvas.pack(side='left', fill='both', expand=True, padx=16, pady=4)
        self.dcanvas.bind('<Button-1>', lambda e: self._on_disproof_click(e, False))
        for seq in self._multi_click_events():
            self.dcanvas.bind(seq, lambda e: self._on_disproof_click(e, True))

    def _show_disproof_pane(self, show):
        if show and not self._dshown:
            self.split.add(self.dframe, stretch='always', minsize=self.px(180))
            self._dshown = True
            self.root.update_idletasks()
            self.split.sash_place(0, 0, int(self.split.winfo_height() * 0.45))
        elif not show and self._dshown:
            self.split.forget(self.dframe)
            self._dshown = False

    def _dsel_world(self):
        d = self.state.disproof
        return d['selected'][0] if d and d['selected'] else None

    def _dcmd(self, cmd):
        self.last_pane = 'disproof'
        self.command('COMMAND ' + cmd)

    @staticmethod
    def _q(s):
        return '"' + s.replace('"', '') + '"'

    def disprove(self):
        """Start a countermodel for the proof's sequent, or for the selected
        goal's sequent if one is selected."""
        if not self.state.proof_title:
            self._set_status('Open a proof first, then look for a countermodel.', 'warn'); return
        self.dsel = []
        self.eng.disproof_selection = []
        self.last_pane = 'disproof'
        num = self.cur_num
        hidden = self.state.disproof is None and self.eng.state(focus=num).disproof is not None
        self.d_open.add(num)
        if hidden and not self.selection:          # closed earlier: just show the blank model again
            self.refresh(); return
        self.command('COMMAND disprove', use_selection=True)

    def _wipe_disproof(self):
        """Back to one blank world, by disproving again and answering "Wipe".
        The engine keeps the old model in its history, so Undo brings it back."""
        self._auto_answer, self._quiet = 0, True
        try:
            self.dsel = []
            self.eng.disproof_selection = []
            self._dcmd('disprove')
        finally:
            self._auto_answer, self._quiet = None, False

    def restart_disproof(self):
        if self.state.disproof is None:
            return
        self._wipe_disproof()
        self._set_status('Countermodel cleared — one blank world again. (Undo brings the old one back.)')

    def close_disproof(self):
        """Put the countermodel away: clear it and hide the pane. For a student
        who opened it by accident, or wants to get back to the proof."""
        d = self.state.disproof
        if d is None:
            return
        if not P.is_blank(d) and not messagebox.askokcancel(
                'PyJape', 'Close the countermodel? The worlds you have built will be cleared.',
                default='cancel'):
            return
        self._wipe_disproof()
        self.d_open.discard(self.cur_num)
        self.last_pane = 'proof'
        self.refresh()
        self._set_status('Countermodel closed.')

    def add_world(self):
        d = self.state.disproof
        sel = self._dsel_world()
        if not d or sel is None:
            self._set_status('Select a world first.', 'warn'); return
        px, py = sel
        ny = py + self.WORLD_DY
        taken = [c for c in d['worlds'] if abs(c[1] - ny) < self.WORLD_DY // 2]
        for k in range(0, 40):
            nx = px + ((k + 1) // 2) * self.WORLD_DX * (1 if k % 2 else -1)
            if all(abs(nx - c[0]) >= self.WORLD_DX * 0.8 for c in taken):
                break
        self._dcmd('addworld %d %d %d %d' % (px, py, nx, ny))
        if (nx, ny) in (self.state.disproof or {}).get('worlds', {}):
            self._dcmd('worldselect %d %d' % (nx, ny))     # so the next tile goes on the new world

    def delete_world(self):
        sel = self._dsel_world()
        if sel is None:
            self._set_status('Select a world first.', 'warn'); return
        self._dcmd('deleteworld %d %d' % sel)

    def add_label(self, text):
        sel = self._dsel_world()
        if sel is None:
            self._set_status('Select a world first (click it), then choose what holds there.', 'warn'); return
        self._dcmd('addworldlabel %d %d %s' % (sel[0], sel[1], self._q(text)))

    def add_custom_label(self):
        text = _expand(self.labelvar.get(), _ESC_FULL).strip()
        if text:
            self.add_label(text)
            self.labelvar.set('')

    def disproof_done(self):
        title = self.state.proof_title
        self._dcmd('done')
        if title and self.state.proof_title != title and not self.state.alert:
            self._set_status('✓ Disproved — %s is recorded as having a countermodel.' % title, 'ok')

    def _on_disproof_click(self, ev, multi):
        d = self.state.disproof
        if not d:
            return
        x = self.dcanvas.canvasx(ev.x); y = self.dcanvas.canvasy(ev.y)
        hit = None
        for it in reversed(self.dcanvas.find_overlapping(x - 3, y - 3, x + 3, y + 3)):
            if it in self.d_pick:
                hit = self.d_pick[it]; break
        if hit is None:
            if self.dsel:                          # click on nothing: drop the formula selection
                self._set_dsel([])
            return
        kind, val = hit
        if kind == 'world':
            sel = self._dsel_world()
            if multi and sel is not None and sel != val:
                lo, hi = (sel, val) if sel[1] < val[1] else (val, sel)
                if lo[1] == hi[1]:
                    self._set_status('Worlds can only be linked upwards: Shift-click a world above or below '
                                     'the selected one.', 'warn'); return
                if hi in d['worlds'][lo]['children']:
                    self._dcmd('deleteworldlink %d %d %d %d' % (lo + hi))
                else:
                    self._dcmd('addworld %d %d %d %d' % (lo + hi))
            else:
                self._dcmd('worldselect %d %d' % val)
        elif kind == 'seq':
            key = '%d %d' % val
            if multi:
                self._set_dsel([s for s in self.dsel if s != key] if key in self.dsel else self.dsel + [key])
            else:
                self._set_dsel([] if self.dsel == [key] else [key])
        elif kind == 'unlabel':
            (wx, wy), text = val
            self._dcmd('deleteworldlabel %d %d %s' % (wx, wy, self._q(text)))

    def _set_dsel(self, sels):
        self.dsel = sels
        self.eng.disproof_selection = list(sels)
        self._dcmd('disproof_selection_change')

    def _disproof_message(self, d):
        if P.is_countermodel(d):
            return ('✓ This is a countermodel: at the selected world every premise holds and the '
                    'conclusion does not. Press Done to record it.')
        hint = ('Click a world to select it, then a formula below to make it hold there. '
                'Shift-click a higher world to link or unlink it. Click a formula in the sequent '
                'to see which worlds it holds at.')
        return hint

    def _draw_disproof(self):
        d = self.state.disproof
        self._show_disproof_pane(d is not None)
        c = self.dcanvas
        c.delete('all')
        self.d_pick = {}
        for w in self.tilebar.winfo_children():
            w.destroy()
        if d is None:
            return
        self.dsel = ['%d %d' % p for p in d['seqsel']]      # the engine's record is authoritative
        self.dmsg.config(text=self._disproof_message(d),
                         fg=PAL['ok'] if P.is_countermodel(d) else PAL['muted'])
        for t in d['tiles']:
            tk.Button(self.tilebar, text=t, font=self.term_small, relief='solid', bd=1,
                      bg='white', fg=PAL['ink'], highlightthickness=0, padx=6, pady=0,
                      command=lambda s=t: self.add_label(s)).pack(side='left', padx=2)

        pad = self.px(16)
        g = self.dpi * self.zoom                     # world drawing scale: grows with the text
        fnt = self.fonts[0]
        asc, desc = fnt.metrics('ascent'), fnt.metrics('descent')
        colour = {'on': PAL['forced'], 'off': PAL['unforced'], 'out': PAL['out'], None: PAL['ink']}
        # -- the sequent strip, each subformula coloured by forcing at the selected world(s).
        # We place the elements ourselves, in the engine's order: it stores the
        # strip's layout when it evaluates the model, so after a text-size change
        # its x positions are stale. Its (x, y) stay the elements' identities.
        base = pad + asc
        x = pad
        for t in sorted(d['seq'], key=lambda t: t['x']):
            tf = self.fonts.get(t['font'], fnt)
            runs = P.forcing_runs(t['raw']) if t['font'] == 0 else [(t['text'], None)]
            x0 = x
            for text, st in runs:
                c.create_text(x, base - asc, text=text, anchor='nw', font=tf, fill=colour[st])
                x += tf.measure(text)
            if t['font'] == 0 and t['cls'] in (1, 2):
                if '%d %d' % (t['x'], t['y']) in self.dsel:
                    c.create_line(x0, base + desc + 2, x, base + desc + 2, fill=PAL['accent'], width=2)
                hit = c.create_rectangle(x0, base - asc, x, base + desc, outline='', fill='')
                self.d_pick[hit] = ('seq', (t['x'], t['y']))
        c.create_text(pad, base + desc + self.zpx(8), anchor='nw', font=self.fonts[1], fill=PAL['muted'],
                      text='green = holds at the selected world     violet = does not hold')

        # -- the worlds: root at the bottom, children above (flip the engine's y)
        R = self.WORLD_R * g
        ws = d['worlds']
        if not ws:
            return
        minx = min(p[0] for p in ws); maxy = max(p[1] for p in ws)
        top = base + desc + self.zpx(8) + self.fonts[1].metrics('linespace') + self.zpx(24)
        def pos(p):                                  # engine coords -> canvas (y flipped, scaled)
            return ((p[0] - minx) * g + pad + R + 4, top + (maxy - p[1]) * g + R)
        for p, wd in ws.items():
            for ch in wd['children']:
                if ch in ws:
                    (x1, y1), (x2, y2) = pos(p), pos(ch)
                    c.create_line(x1, y1, x2, y2, fill=PAL['ink'], width=1.5 * self.dpi)
        lab_font = self.term_small
        lh = lab_font.metrics('linespace')
        for p, wd in ws.items():
            x, y = pos(p)
            chosen = p in d['selected']
            fill = 'white'
            if self.dsel:
                fill = PAL['forcedbg'] if wd['forced'] else PAL['unforcedbg']
            oval = c.create_oval(x - R, y - R, x + R, y + R, fill=fill,
                                 outline=PAL['accent'] if chosen else PAL['ink'],
                                 width=(3 if chosen else 1.5) * self.dpi)
            self.d_pick[oval] = ('world', p)
            for i, (_, text) in enumerate(wd['labels']):
                tx, ty = x + R + self.px(6), y - (len(wd['labels']) * lh) / 2 + i * lh
                item = c.create_text(tx, ty, text=text, anchor='nw', font=lab_font, fill=PAL['ink'])
                self.d_pick[item] = ('world', p)
                bx = c.bbox(item)[2] + self.px(8)
                xi = c.create_text(bx, ty + 2, text='×', anchor='nw', font=self.fonts[1], fill=PAL['muted'])
                self.d_pick[xi] = ('unlabel', (p, text))
        bbox = c.bbox('all')
        if bbox:
            c.configure(scrollregion=(0, 0, bbox[2] + pad, bbox[3] + pad))

    # ---- chrome ----------------------------------------------------------
    def _rebuild_menus(self):
        for w in self.menu_holder.winfo_children():
            w.destroy()
        for name, items in self.state.menus.items():
            if not items:
                continue
            mb = tk.Menubutton(self.menu_holder, text=name, relief='flat', bg=PAL['bg'], fg=PAL['ink'])
            m = tk.Menu(mb, tearoff=0)
            for it in items:
                cmd = it['command']
                m.add_command(label=it['label'] or '(item)',
                              command=lambda c=cmd: self._menu_command(c))
            mb.configure(menu=m)
            mb.pack(side='left', padx=2)

    # Menu items that drive the disproof pane, not a proof rule (so they skip the
    # "rule didn't apply" check, and route Undo to the countermodel).
    _DISPROOF_MENU = {'disprove', 'done'}

    def _menu_command(self, cmd):
        if cmd.strip() == 'disprove':
            self.disprove()
        elif cmd.strip() in self._DISPROOF_MENU:
            self.command('COMMAND ' + cmd, use_selection=True)
        else:
            self.last_pane = 'proof'
            self.command('COMMAND ' + cmd, use_selection=True, is_rule=True)

    def _rebuild_panels(self):
        names = [n for n, e in self.state.panels.items() if e]
        names.sort(key=lambda n: (n != MINE, n != 'Conjectures', n))   # Saved first, then Conjectures
        if self.active_panel not in names:
            self.active_panel = (MINE if MINE in names
                                 else ('Conjectures' if 'Conjectures' in names else (names[0] if names else None)))
        for w in self.tabs.winfo_children():
            w.destroy()
        for n in names:
            b = tk.Button(self.tabs, text=re.sub(r' conjectures$', '', n, flags=re.I),
                          relief='flat', font=self.f['body'],
                          bg=(PAL['accent'] if n == self.active_panel else PAL['bg']),
                          fg=('white' if n == self.active_panel else PAL['muted']),
                          command=lambda nm=n: self._switch_panel(nm))
            b.pack(side='left', padx=2)
        # dedupe by display (a reloaded .jp can re-add an existing conjecture)
        seen, self._cur_entries = set(), []
        for e in self.state.panels.get(self.active_panel, []):
            if e['display'] not in seen:
                seen.add(e['display']); self._cur_entries.append(e)
        self.exlist.delete(0, 'end')
        for e in self._cur_entries:
            mark = ('  ✓' if e.get('proved') else '') + ('  ⊭' if e.get('disproved') else '')
            self.exlist.insert('end', e['display'] + mark)

    def _switch_panel(self, name):
        self.active_panel = name
        self._rebuild_panels()

    # ---- "what we know" --------------------------------------------------
    def _known_panel(self):
        for w in self.known.winfo_children():
            w.destroy()
        if not self.state.proof_title:
            self.known_lbl.pack_forget(); self.known.pack_forget()
            return
        # place both sections just above the EXERCISES heading
        self.known_lbl.pack(anchor='w', padx=14, pady=(6, 2), before=self.ex_label)
        self.known.pack(fill='x', padx=14, before=self.ex_label)

        if self.state.disproof is not None:        # a Kripke model: show how to read it instead
            self.known_lbl.config(text='READING A COUNTERMODEL')
            self._forcing_legend()
            return
        self.known_lbl.config(text='WHAT WE KNOW')

        # Only the hypotheses in scope at the line being worked on (the selected
        # formula, else the current open goal; premises only once it's proved).
        # A hypothesis from a box that has already closed is NOT known here.
        facts = L.facts_in_scope(self.state.texts, self.state.rects, self.selection)
        title = self.state.proof_title
        ti = title.find('⊢')
        premises = set(p.replace(' ', '') for p in (title[:ti].split(',') if ti >= 0 else []) if p.strip())
        goal_str = (title[ti + 1:] if ti >= 0 else title).strip()

        fact_objs = [(s, L.parse(s)) for s in facts]
        goal = (goal_str, L.parse(goal_str)) if goal_str else None

        # When several goals are open, name which case these facts belong to so
        # the two scopes aren't confused (the active line is marked in the proof).
        gtext, gi, gtot = L.active_case(self.state.texts, self.state.rects, self.selection)
        if gtot > 1 and gtext:
            assumed = [s for s in facts if s.replace(' ', '') not in premises]
            cap = 'proving %s' % gtext + (' — assuming %s' % ', '.join(assumed) if assumed else '')
            hdr = tk.Frame(self.known, bg=PAL['bg']); hdr.pack(anchor='w', fill='x', pady=(0, 2))
            tk.Label(hdr, text=cap, bg=PAL['bg'], fg=PAL['ink'], font=self.f['heading'],
                     wraplength=self._wrap() - self.px(80), justify='left').pack(side='left')
            tk.Label(hdr, text='case %d of %d' % (gi, gtot), bg=PAL['bg'], fg=PAL['accent'],
                     font=self.f['small']).pack(side='right')
            tk.Label(self.known, text='Click another goal to switch cases.',
                     bg=PAL['bg'], fg=PAL['muted'], font=self.f['small']).pack(anchor='w', pady=(0, 3))

        if not facts:
            tk.Label(self.known, text='Nothing known yet — make an assumption or forward step.',
                     bg=PAL['bg'], fg=PAL['muted'], font=self.f['body'], wraplength=self._wrap(),
                     justify='left').pack(anchor='w')
        for s in facts:
            r = tk.Frame(self.known, bg=PAL['bg']); r.pack(anchor='w', fill='x')
            tk.Label(r, text=s, bg=PAL['bg'], fg=PAL['ink'], font=self.term_small).pack(side='left')
            tag = 'premise' if s.replace(' ', '') in premises else 'assumed / derived'
            tk.Label(r, text=tag, bg=PAL['bg'], fg=PAL['muted'], font=self.f['small']).pack(side='left', padx=6)

        # --- truth table: a toggle, capped to keep it light -------------------
        SAFE, HARD = 6, 10               # auto-show up to 2^6=64 rows; opt-in up to 2^10
        # reset the per-proof "compute anyway" override when the proof changes
        if self._table_for != title:
            self._table_for = title
            self.force_big = False

        tk.Checkbutton(self.known, text='Show truth table', variable=self.show_table,
                       command=self._known_panel, bg=PAL['bg'], fg=PAL['muted'],
                       activebackground=PAL['bg'], activeforeground=PAL['ink'],
                       selectcolor='white', font=self.f['body'],
                       highlightthickness=0, bd=0, anchor='w').pack(anchor='w', pady=(6, 0))
        if not self.show_table.get():
            return

        # count variables cheaply first — never build 2^N rows just to find N is huge
        tatoms = set()
        for _, a in fact_objs:
            if a and 'error' not in a and not a.get('firstOrder'):
                L.atoms_of(a, tatoms)
        if goal and goal[1] and 'error' not in goal[1] and not goal[1].get('firstOrder'):
            L.atoms_of(goal[1], tatoms)
        nvar = len(tatoms)

        if nvar == 0:
            tk.Label(self.known, text='Truth tables apply to propositional logic; use the facts above.',
                     bg=PAL['bg'], fg=PAL['muted'], font=self.f['body'], wraplength=self._wrap(),
                     justify='left').pack(anchor='w', pady=(4, 0))
            return
        if nvar > HARD or (nvar > SAFE and not self.force_big):
            box = tk.Frame(self.known, bg=PAL['bg']); box.pack(anchor='w', fill='x', pady=(2, 0))
            tk.Label(box, text='%d variables (%d rows) — table hidden to keep things fast.'
                     % (nvar, 2 ** nvar), bg=PAL['bg'], fg=PAL['muted'], font=self.f['body'],
                     wraplength=self._wrap(), justify='left').pack(anchor='w')
            if nvar <= HARD:
                tk.Button(box, text='Compute anyway', font=self.f['small'], relief='flat',
                          bg=PAL['bg'], fg=PAL['accent'], highlightbackground=PAL['bg'],
                          command=self._force_table).pack(anchor='w')
            return

        tbl = L.build_table(fact_objs, goal, cap=HARD)
        self._draw_table(tbl)
        if tbl.goal:
            unmodelled = any(a and (a.get('firstOrder') or 'error' in a) for _, a in fact_objs)
            if tbl.consistent_count == 0:
                msg = 'No world fits — the assumptions contradict.'
            elif tbl.goal_holds_in_all:
                msg = 'In every world that fits, %s is true.' % tbl.goal[0]
            elif not unmodelled:
                ce = tbl.counterexample
                vals = ', '.join('%s=%s' % (a, 'T' if ce['v'][a] else 'F') for a in tbl.atoms)
                msg = 'A world fits where %s is false (%s).' % (tbl.goal[0], vals)
            else:
                msg = 'Some table rows make %s false, but quantified facts may rule those out.' % tbl.goal[0]
            tk.Label(self.known, text=msg, bg=PAL['bg'], fg=PAL['ink'], font=self.f['body'],
                     wraplength=self._wrap(), justify='left').pack(anchor='w', pady=(4, 6))

    _FORCING = [
        ('A world', 'a state of knowledge. Lines go up to the worlds it can still grow into.'),
        ('Atoms', 'P holds at a world if P is written there; it then holds at every world above.'),
        ('A∧B, A∨B', 'hold if both / one of A and B hold at this world.'),
        ('A→B', 'holds if B holds at every world (here or above) where A holds.'),
        ('¬A', 'holds if A holds at no world here or above.'),
        ('∀x.P(x)', 'holds if P(i) holds for every individual i at every world here or above.'),
        ('∃x.P(x)', 'holds if P(i) holds here for some individual i ("actual i") of this world.'),
        ('Goal', 'select a world where every premise holds but the conclusion does not.'),
    ]

    def _forcing_legend(self):
        for head, text in self._FORCING:
            r = tk.Frame(self.known, bg=PAL['bg']); r.pack(anchor='w', fill='x', pady=1)
            tk.Label(r, text=head, bg=PAL['bg'], fg=PAL['ink'], font=self.term_small, width=9,
                     anchor='nw', justify='left').pack(side='left', anchor='n')
            tk.Label(r, text=text, bg=PAL['bg'], fg=PAL['muted'], font=self.f['body'],
                     wraplength=self._wrap() - self.term_small.measure('0' * 9) - self.px(8),
                     justify='left', anchor='w').pack(side='left', fill='x')

    def _force_table(self):
        """Opt in to computing a larger (7–10 variable) table for this proof."""
        self.force_big = True
        self._known_panel()

    def _draw_table(self, tbl):
        grid = tk.Frame(self.known, bg=PAL['bg']); grid.pack(anchor='w', pady=(6, 2))
        # A fact that is a bare atom (e.g. "E") already has an atom column, so
        # don't repeat it as a fact column — that caused "E F F E …" headers.
        fcols = [i for i, (_, a) in enumerate(tbl.prop_facts) if a and 'atom' not in a]
        cols = list(tbl.atoms) + [tbl.prop_facts[i][0] for i in fcols] + ([tbl.goal[0]] if tbl.goal else [])
        for ci, name in enumerate(cols):
            tk.Label(grid, text=name, bg=PAL['bg'], fg=PAL['muted'],
                     font=self.f['heading']).grid(row=0, column=ci, padx=3)
        for ri, row in enumerate(tbl.rows, start=1):
            fit = row['consistent']
            rbg = PAL['okbg'] if fit else PAL['bg']
            fg = PAL['ink'] if fit else PAL['out']
            ci = 0
            for a in tbl.atoms:
                tk.Label(grid, text='T' if row['v'][a] else 'F', bg=rbg, fg=fg,
                         font=self.f['body']).grid(row=ri, column=ci, sticky='nsew', padx=1); ci += 1
            for i in fcols:
                val = row['fact_vals'][i]
                tk.Label(grid, text='✓' if val else '✗', bg=rbg,
                         fg=(PAL['ok'] if val else PAL['out']),
                         font=self.f['body']).grid(row=ri, column=ci, sticky='nsew', padx=1); ci += 1
            if tbl.goal:
                gv = ('T' if row['goal_val'] else 'F') if fit else '·'
                tk.Label(grid, text=gv, bg=rbg, fg=(PAL['ok'] if (fit and row['goal_val']) else fg),
                         font=self.f['heading']).grid(row=ri, column=ci, sticky='nsew', padx=1)

    # ---- misc ------------------------------------------------------------
    def _live_escape(self, *_):
        before = self.newvar.get()
        after = _expand(before, _ESC_LIVE)
        if after != before:
            pos = self.newentry.index('insert')
            self.newvar.set(after)
            self.newentry.icursor(max(0, pos - (len(before) - len(after))))

    # Blue is the ordinary (info) colour; red is reserved for errors so it stands out.
    _STATUS_FG = {'info': PAL['accent'], 'warn': PAL['amber'], 'error': PAL['red'], 'ok': PAL['ok']}

    def _set_status(self, s, kind='info'):
        self.status.config(text=s, fg=self._STATUS_FG.get(kind, PAL['accent']))


def main():
    engine_path, entry = E.default_paths()
    _enable_dpi_awareness()          # before Tk exists, or Windows blurs the text
    root = tk.Tk()
    JapeApp(root, engine_path, entry)
    root.mainloop()


if __name__ == '__main__':
    main()
