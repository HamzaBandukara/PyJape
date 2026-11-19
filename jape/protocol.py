"""Jape's GUI line protocol: the same field splitter the engine uses, plus a
parser that turns the engine's draw/menu/panel output into a renderable state
(one State per call, covering every open proof window)."""


def japesplit(line):
    """Faithful port of the engine's Dispatcher.japesplit:
       "  toggles string-quoting and is dropped
       space separates fields
       \\n -> newline, \\NNN -> octal char, \\<c> -> literal c (so \\" -> ")"""
    out, buf, i, n = [], [], 0, len(line)
    while i < n:
        c = line[i]; i += 1
        if c == '"':
            pass                                   # quote: dropped
        elif c == ' ':
            if buf:
                out.append(''.join(buf)); buf = []
        elif c == '\\' and i < n:
            d = line[i]; i += 1
            if d == 'n':
                buf.append('\n')
            elif '0' <= d <= '8' and i + 1 < n:
                code = ((ord(d) - 48) * 8 + (ord(line[i]) - 48)) * 8 + (ord(line[i + 1]) - 48)
                i += 2
                buf.append(chr(code))
            else:
                buf.append(d)
        else:
            buf.append(c)
    if buf:
        out.append(''.join(buf))
    return out


def strip_controls(s):
    return ''.join(ch for ch in s if ord(ch) >= 0x20)


# In a disproof sequent the engine brackets every subformula with invisible
# characters saying whether it is forced at the selected world(s):
#   \001…\002 forced ("on"), \003…\004 not forced ("off"),
#   \005…\006 not evaluated ("out": e.g. P(x) under a binder).
# \024…\025 ("lock") mark subformulas whose value can't change in worlds above;
# they don't change the colour. See engine_src/invisibles.ml and disproof.ml.
_OPEN = {'\x01': 'on', '\x03': 'off', '\x05': 'out'}
_CLOSE = {'\x02', '\x04', '\x06'}


def forcing_runs(raw):
    """Split a disproof-pane string into [(text, state)] runs, where state is the
    innermost forcing bracket around the text: 'on', 'off', 'out' or None.
    An 'out' part (e.g. the body P(x) of ∀x.P(x), which has no value on its
    own) takes the colour of the formula around it, so a student sees the
    whole of ∀x.P(x) as forced or not; it stays 'out' only at top level."""
    runs, stack, buf = [], [], []

    def flush():
        if buf:
            known = [x for x in stack if x != 'out']
            st = known[-1] if known else (stack[-1] if stack else None)
            if runs and runs[-1][1] == st:
                runs[-1] = (runs[-1][0] + ''.join(buf), st)
            else:
                runs.append((''.join(buf), st))
            buf.clear()

    for ch in raw:
        if ch in _OPEN:
            flush(); stack.append(_OPEN[ch])
        elif ch in _CLOSE:
            flush()
            if stack:
                stack.pop()
        elif ord(ch) >= 0x20:
            buf.append(ch)
    flush()
    return runs


def new_disproof():
    """One window's Kripke countermodel, as last drawn by the engine.
    Coordinates are the engine's own: they identify worlds and sequent
    elements, and must be sent back unchanged in commands. A child world
    always has a greater y than its parent (the engine's y axis points up)."""
    return {
        'seqbox': None,      # (width, ascent, descent) of the sequent strip
        'seq': [],           # {x,y,font,cls,text,raw}: the sequent, font 0 = formula
        'emph': {},          # (x,y) of a sequent element -> forced at the selected world(s)?
        'tiles': [],         # formulas the student can put on a world
        'worlds': {},        # (x,y) -> {'forced': bool, 'labels': [(forced, text)], 'children': [(x,y)]}
        'selected': [],      # world coords currently selected
        'seqsel': [],        # sequent element coords selected (engine-forced selection)
    }


def is_countermodel(d):
    """True when, at the selected world(s), every hypothesis is forced and the
    conclusion is not: that is, the model disproves the sequent."""
    if not d or not d['seq']:
        return False
    hyps = [t for t in d['seq'] if t['font'] == 0 and t['cls'] == 2]
    concs = [t for t in d['seq'] if t['font'] == 0 and t['cls'] == 1]
    if not concs:
        return False
    e = d['emph']
    return (all(e.get((t['x'], t['y'])) is True for t in hyps)
            and all(e.get((t['x'], t['y'])) is False for t in concs))


def is_blank(d):
    """A fresh model: one world with nothing on it. That's what the engine holds
    after "start again"; PyJape hides it unless the student opened it."""
    return bool(d) and len(d['worlds']) == 1 and not any(w['labels'] for w in d['worlds'].values())


class State:
    def __init__(self):
        self.focus = None        # window num currently shown
        self.texts = []          # {x,y,font,cls,text}  — the FOCUSED window
        self.lines = []          # {x1,y1,x2,y2}
        self.rects = []          # {x,y,w,h}
        self.menus = {}          # name -> [{label,command}]
        self.panels = {}         # name -> [{display,command}]
        self.selected = None     # {panel,name}
        self.alert = None
        self.proof_title = None
        self.disproof = None     # the focused window's countermodel (see new_disproof), or None
        self.marks = {}          # (panel, command) -> (proved, disproved)
        self.windows = {}        # num(str) -> {texts,lines,rects,title,disproof}  (all open proof windows)
        self.latest = None       # most-recently-opened window num


def parse_transcript(text, focus=None):
    """Window-aware. Jape is multi-window: each OPENPROOF is a window and draws
    target the current pane. We keep every window's drawings so we can show any
    one. `focus` picks which window's drawings become texts/lines/rects/title;
    default is the most-recently-opened.

    Each window has two panes (DRAWINPANE 0 = the proof, 1 = the disproof).
    Proof drawings go to the window's texts/lines/rects; disproof drawings and
    the world/tile lines go to its 'disproof' record (see new_disproof)."""
    st = State()
    curm = None                                    # in-progress DRAWMEASUREDTEXT
    win = None                                      # window number draws currently target
    pane = 0                                        # pane draws currently target

    def w():                                        # current window's buffer (or a scratch)
        return st.windows.get(win)

    def pw():                                       # the proof buffer, if draws target it
        return w() if pane == 0 else None

    def dp():                                       # the current window's disproof, if any
        cw = w()
        return cw.get('disproof') if cw is not None else None

    def close(num):
        nonlocal win
        st.windows.pop(num, None)
        if win == num:
            win = None
        if st.latest == num:
            st.latest = next(iter(st.windows), None)

    def add_text(t):
        if pane == 0:
            if pw() is not None:
                pw()['texts'].append(t)
        elif dp() is not None:
            dp()['seq'].append(t)

    for raw in text.split('\n'):
        if not raw:
            continue
        sp = raw.find(' ')
        head = raw if sp < 0 else raw[:sp]
        if head == 'CLEARPANE':
            f = japesplit(raw)
            which = f[1] if len(f) > 1 else '0'
            if w() is not None:
                if which == '1':
                    w()['disproof'] = None
                else:
                    w()['texts'], w()['lines'], w()['rects'] = [], [], []
            st.alert = None          # a redraw means the last action succeeded; drop a stale alert
        elif head == 'DRAWINPANE':
            f = japesplit(raw)
            pane = 1 if len(f) > 1 and f[1] == '1' else 0
        elif head == 'OPENPROOF':
            f = japesplit(raw)
            win = f[2] if len(f) > 2 else '0'
            st.windows[win] = {'texts': [], 'lines': [], 'rects': [], 'disproof': None,
                               'title': strip_controls(f[1] if len(f) > 1 else '')}
            st.latest = win
            pane = 0
        elif head in ('CLOSEPROOF', 'CLOSEPROOFSONE'):
            f = japesplit(raw)
            close(f[1] if len(f) > 1 else win)
        elif head == '__FOCUS__':                 # synthetic: our own setfocus (draws now target it)
            num = raw.split(' ', 1)[1] if sp >= 0 else None
            if num in st.windows:
                win = num; st.latest = num
        elif head == 'DRAWSTRING':
            f = japesplit(raw)                     # DRAWSTRING x y font class text
            rawtext = ' '.join(f[5:])
            t = strip_controls(rawtext)
            if t:
                add_text({'x': int(f[1]), 'y': int(f[2]), 'font': int(f[3]),
                          'cls': int(f[4]), 'text': t, 'raw': rawtext})
        elif head == 'DRAWMEASUREDTEXT':
            f = japesplit(raw)                     # x y class length
            curm = {'x': int(f[1]), 'y': int(f[2]), 'cls': int(f[3]), 'text': '', 'raw': '', 'font': 0}
        elif head == 'DRAWMT':
            f = japesplit(raw)                     # x y font segment
            if curm is not None:
                seg = ' '.join(f[4:])
                curm['text'] += strip_controls(seg); curm['raw'] += seg; curm['font'] = int(f[3])
        elif head == 'DRAWMEASUREDTEXTEND':
            if curm is not None and curm['text']:
                add_text(dict(curm))
            curm = None
        elif head == 'DRAWLINE':
            f = japesplit(raw)
            if pw() is not None:
                pw()['lines'].append({'x1': int(f[1]), 'y1': int(f[2]), 'x2': int(f[3]), 'y2': int(f[4])})
        elif head == 'DRAWRECT':
            f = japesplit(raw)
            if pw() is not None:
                pw()['rects'].append({'x': int(f[1]), 'y': int(f[2]), 'w': int(f[3]), 'h': int(f[4])})
        # ---- the disproof pane: every redraw starts with SEQBOX ----------------
        elif head == 'SEQBOX':
            f = japesplit(raw)                     # SEQBOX width ascent descent
            if w() is not None:
                d = new_disproof()
                d['seqbox'] = tuple(int(v) for v in f[1:4])
                w()['disproof'] = d
            st.alert = None
        elif head == 'EMPHASISE':
            f = japesplit(raw)                     # EMPHASISE x y forced
            if dp() is not None:
                dp()['emph'][(int(f[1]), int(f[2]))] = (f[3] == 'T')
        elif head == 'TILESSTART':
            if dp() is not None:
                dp()['tiles'] = []
        elif head == 'TILE':
            f = japesplit(raw)
            if dp() is not None:
                dp()['tiles'].append(strip_controls(' '.join(f[1:])))
        elif head == 'WORLDSSTART':
            if dp() is not None:
                dp()['worlds'], dp()['selected'] = {}, []
        elif head == 'WORLD':
            f = japesplit(raw)                     # WORLD x y forced
            if dp() is not None:
                dp()['worlds'][(int(f[1]), int(f[2]))] = {
                    'forced': f[3] == 'T', 'labels': [], 'children': []}
        elif head == 'WORLDLABEL':
            f = japesplit(raw)                     # WORLDLABEL x y forced label
            wd = dp()['worlds'].get((int(f[1]), int(f[2]))) if dp() is not None else None
            if wd is not None:
                wd['labels'].append((f[3] == 'T', strip_controls(' '.join(f[4:]))))
        elif head == 'WORLDCHILD':
            f = japesplit(raw)                     # WORLDCHILD x y childx childy
            wd = dp()['worlds'].get((int(f[1]), int(f[2]))) if dp() is not None else None
            if wd is not None:
                wd['children'].append((int(f[3]), int(f[4])))
        elif head == 'WORLDSELECT':
            f = japesplit(raw)
            if dp() is not None:
                dp()['selected'].append((int(f[1]), int(f[2])))
        elif head == 'DISPROOFSELECT':
            f = japesplit(raw)
            if dp() is not None:
                dp()['seqsel'].append((int(f[1]), int(f[2])))
        # ---- menus, panels, alerts ---------------------------------------------
        elif head == 'EMPTYMENUSANDPANELS':
            st.menus.clear(); st.panels.clear()
        elif head == 'NEWMENU':
            f = japesplit(raw)
            st.menus.setdefault(f[1], [])
        elif head == 'MENUITEM':
            f = japesplit(raw)                     # menu label key command enabled
            st.menus.setdefault(f[1], []).append(
                {'label': strip_controls(f[2] if len(f) > 2 else ''), 'command': f[4] if len(f) > 4 else ''})
        elif head == 'NEWPANEL':
            f = japesplit(raw)
            st.panels.setdefault(f[1], [])
        elif head == 'PANELENTRY':
            f = japesplit(raw)                     # panel display command
            st.panels.setdefault(f[1], []).append(
                {'display': strip_controls(f[2] if len(f) > 2 else ''),
                 'command': f[3] if len(f) > 3 else (f[2] if len(f) > 2 else '')})
        elif head == 'MARKPANELENTRY':
            f = japesplit(raw)                     # panel command proved disproved
            if len(f) > 4:
                st.marks[(f[1], f[2])] = (f[3] == 'T', f[4] == 'T')
        elif head == 'SELECTPANELENTRY':
            f = japesplit(raw)                     # panel name
            st.selected = {'panel': f[1], 'name': f[2] if len(f) > 2 else ''}
        elif head == 'ASKNOW':
            f = japesplit(raw)
            st.alert = strip_controls(f[2] if len(f) > 2 else '')
        elif head == 'SETALERT':
            f = japesplit(raw)
            st.alert = strip_controls(' '.join(f[1:]))

    # proved/disproved marks onto the panel entries they name
    for pname, entries in st.panels.items():
        for e in entries:
            e['proved'], e['disproved'] = st.marks.get((pname, e['command']), (False, False))

    # expose the focused window (requested, else the latest) as the view
    fv = focus if focus in st.windows else st.latest
    if fv is not None and fv in st.windows:
        wv = st.windows[fv]
        st.texts, st.lines, st.rects, st.proof_title = wv['texts'], wv['lines'], wv['rects'], wv['title']
        st.disproof = wv['disproof']
        st.focus = fv
    else:
        st.focus = None
    return st


def open_windows(lines):
    """name -> window number for every proof window still open (OPENPROOF minus
    CLOSEPROOF), from the raw protocol lines."""
    wins = {}
    for ln in lines:
        if ln.startswith('OPENPROOF'):
            f = japesplit(ln)
            if len(f) > 2:
                wins[strip_controls(f[1])] = f[2]
        elif ln.startswith('CLOSEPROOF'):          # CLOSEPROOF n, or CLOSEPROOFSONE n
            f = japesplit(ln)
            num = f[1] if len(f) > 1 else None
            for k, v in list(wins.items()):
                if v == num:
                    del wins[k]
    return wins


def conjecture_command(state, panel, name):
    entries = state.panels.get(panel, [])
    for e in entries:
        if e['display'] == name:
            return e['command']
    return entries[-1]['command'] if entries else None
