"""Logic behind the "What we know" panel.

- Scope: work out which hypotheses are available at the line being worked on,
  from the proof's drawn boxes (open_goals, scope_target, in_scope,
  facts_in_scope).
- Truth tables: parse the connectives Jape uses, evaluate them under a
  valuation, and build the possible-worlds table. Tables are propositional
  only; a formula with a quantifier or a predicate application is flagged
  first-order and gets no table.

Pure functions with no tkinter, so they can be tested headlessly."""
import re
import itertools

_FO = re.compile(r'[∀∃]|[A-Za-z][A-Za-z0-9_\']*\s*\(')


def is_first_order(s):
    return bool(_FO.search(s))


def _tokenize(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in ' \t':
            i += 1; continue
        if c in '→∧∨¬⊤⊥↔()':
            toks.append(c); i += 1; continue
        if c.isalpha():
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] in "_'"):
                j += 1
            toks.append(('atom', s[i:j])); i = j; continue
        raise ValueError(f'unexpected character “{c}”')
    return toks


def parse(s):
    """Return an AST dict, or {'error':..} / {'firstOrder':True}.
    AST: {'atom':name} | {'const':bool} | {'op':'not','a':..}
         | {'op':'and'|'or'|'imp'|'iff','a':..,'b':..}
    Precedence low->high: ↔ , →(right) , ∨ , ∧ , ¬ , atom/()."""
    if is_first_order(s):
        return {'firstOrder': True}
    try:
        toks = _tokenize(s)
    except ValueError as e:
        return {'error': str(e)}
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def parse_iff():
        a = parse_imp()
        while peek() == '↔':
            pos[0] += 1; a = {'op': 'iff', 'a': a, 'b': parse_imp()}
        return a

    def parse_imp():
        a = parse_or()
        if peek() == '→':
            pos[0] += 1; return {'op': 'imp', 'a': a, 'b': parse_imp()}   # right-assoc
        return a

    def parse_or():
        a = parse_and()
        while peek() == '∨':
            pos[0] += 1; a = {'op': 'or', 'a': a, 'b': parse_and()}
        return a

    def parse_and():
        a = parse_not()
        while peek() == '∧':
            pos[0] += 1; a = {'op': 'and', 'a': a, 'b': parse_not()}
        return a

    def parse_not():
        if peek() == '¬':
            pos[0] += 1; return {'op': 'not', 'a': parse_not()}
        return parse_atom()

    def parse_atom():
        t = peek()
        if t == '(':
            pos[0] += 1; e = parse_iff()
            if peek() != ')':
                raise ValueError('missing )')
            pos[0] += 1; return e
        if t == '⊤':
            pos[0] += 1; return {'const': True}
        if t == '⊥':
            pos[0] += 1; return {'const': False}
        if isinstance(t, tuple) and t[0] == 'atom':
            pos[0] += 1; return {'atom': t[1]}
        raise ValueError('expected a formula')

    try:
        ast = parse_iff()
        if pos[0] != len(toks):
            return {'error': 'unexpected token'}
        return ast
    except ValueError as e:
        return {'error': str(e)}


def atoms_of(ast, acc=None):
    acc = set() if acc is None else acc
    if not ast or 'error' in ast or ast.get('firstOrder'):
        return acc
    if 'atom' in ast:
        acc.add(ast['atom'])
    elif ast.get('op') == 'not':
        atoms_of(ast['a'], acc)
    elif 'a' in ast:
        atoms_of(ast['a'], acc); atoms_of(ast['b'], acc)
    return acc


def eval_ast(ast, v):
    if 'atom' in ast:
        return bool(v[ast['atom']])
    if 'const' in ast:
        return ast['const']
    op = ast['op']
    if op == 'not':
        return not eval_ast(ast['a'], v)
    a = eval_ast(ast['a'], v); b = eval_ast(ast['b'], v)
    if op == 'and':
        return a and b
    if op == 'or':
        return a or b
    if op == 'imp':
        return (not a) or b
    if op == 'iff':
        return a == b
    raise ValueError('bad ast')


class Table:
    pass


def build_table(facts, goal, cap=6):   # 2^6 = 64 rows — keep tables light by default
    """facts: [(text, ast)]; goal: (text, ast) | None. Returns a Table with
    atoms, rows (each: v, fact_vals, consistent, goal_val), consistent_count,
    goal_holds_in_all, counterexample, tooBig/empty flags."""
    prop_facts = [(t, a) for (t, a) in facts if a and 'error' not in a and not a.get('firstOrder')]
    atoms = set()
    for _, a in prop_facts:
        atoms_of(a, atoms)
    goal_prop = goal if (goal and goal[1] and 'error' not in goal[1] and not goal[1].get('firstOrder')) else None
    if goal_prop:
        atoms_of(goal_prop[1], atoms)
    atoms = sorted(atoms)

    res = Table()
    res.atoms = atoms
    res.prop_facts = prop_facts
    res.goal = goal_prop
    res.empty = (len(atoms) == 0)
    res.too_big = (len(atoms) > cap)
    res.rows = []
    res.consistent_count = 0
    res.goal_holds_in_all = False
    res.counterexample = None
    if res.empty or res.too_big:
        return res

    consistent_rows = []
    for bits in itertools.product([False, True], repeat=len(atoms)):
        v = dict(zip(atoms, bits))
        fact_vals = [eval_ast(a, v) for _, a in prop_facts]
        consistent = all(fact_vals)
        goal_val = eval_ast(goal_prop[1], v) if goal_prop else None
        row = {'v': v, 'fact_vals': fact_vals, 'consistent': consistent, 'goal_val': goal_val}
        res.rows.append(row)
        if consistent:
            consistent_rows.append(row)
    res.consistent_count = len(consistent_rows)
    if goal_prop and consistent_rows:
        res.goal_holds_in_all = all(r['goal_val'] for r in consistent_rows)
        for r in consistent_rows:
            if not r['goal_val']:
                res.counterexample = r
                break
    return res


# ---- box (Fitch) scope: which hypotheses are known at a given line ----------
# Jape draws a box proof as text runs (font 0: formulas with class 2=hypothesis,
# 1=conclusion) inside DRAWRECT boxes, with font-1 annotations (class 3 = the
# rule name that justifies a proved line). A hypothesis is "known" at a target
# line only if it is above the target and every box enclosing the hypothesis
# also encloses the target — i.e. its box hasn't closed before the target. This
# is what makes ~F in a sibling/closed box NOT count at the line you're proving.

def _rect_has(r, px, py, m=2):
    return (r['x'] - m) <= px <= (r['x'] + r['w'] + m) and \
           (r['y'] - m) <= py <= (r['y'] + r['h'] + m)


def _justified_ys(texts):
    """y-coords of lines carrying a rule-name justification (class-3 annotation);
    a conclusion on such a line is proved, one without it is still an open goal."""
    return {t['y'] for t in texts if t['font'] == 1 and t['cls'] == 3}


def open_goals(texts):
    """Unproved conclusions: class-1 formulas whose line has no justification,
    sorted top-to-bottom."""
    jy = _justified_ys(texts)
    og = [t for t in texts if t['font'] == 0 and t['cls'] == 1 and t['y'] not in jy]
    return sorted(og, key=lambda t: (t['y'], t['x']))


def enclosing_boxes(rects, px, py):
    """Indices of the boxes that contain point (px,py) — a line's box-scope
    signature. Two lines with the same signature are in the same sub-proof."""
    return frozenset(i for i, r in enumerate(rects) if _rect_has(r, px, py))


def active_case(texts, rects, selection):
    """When several goals are open, which one the panel's scope refers to.
    Returns (goal_text, index_1based, total). The active goal is the open goal
    sharing the target line's box (so a selection in one branch names that
    branch); with nothing selected it's the first open goal. total<=1 means no
    ambiguity to label."""
    og = open_goals(texts)
    if not og:
        return (None, 0, 0)
    tgt = scope_target(texts, selection)
    if tgt is None:
        return (None, 0, len(og))
    sig = enclosing_boxes(rects, *tgt)
    same = [g for g in og if enclosing_boxes(rects, g['x'], g['y']) == sig]
    active = same[0] if same else og[0]
    return (active['text'], og.index(active) + 1, len(og))


def is_complete(texts):
    """True when there's a proof drawn and no goals remain open."""
    return any(t['font'] == 0 and t['cls'] == 1 for t in texts) and not open_goals(texts)


def scope_target(texts, selection):
    """The line to compute scope at: the selected formula, else the first (top)
    open goal, else the root conclusion (bottom) for a finished proof. Returns
    (x, y) or None. `selection` is a list of {x,y[,cls]} dicts."""
    if selection:
        s = selection[0]
        return (s['x'], s['y'])
    og = open_goals(texts)
    if og:
        t = min(og, key=lambda t: t['y'])
        return (t['x'], t['y'])
    concl = [t for t in texts if t['font'] == 0 and t['cls'] == 1]
    if concl:
        t = max(concl, key=lambda t: t['y'])
        return (t['x'], t['y'])
    return None


def in_scope(rects, hx, hy, tx, ty):
    """Is a hypothesis at (hx,hy) in scope at target (tx,ty)? It must be at or
    above the target, and no box may enclose the hypothesis without also
    enclosing the target (that box would have closed in between)."""
    if hy > ty:
        return False
    for r in rects:
        if _rect_has(r, hx, hy) and not _rect_has(r, tx, ty):
            return False
    return True


def facts_in_scope(texts, rects, selection):
    """Ordered, de-duplicated hypothesis texts known at the current line."""
    tgt = scope_target(texts, selection)
    if tgt is None:
        return []
    tx, ty = tgt
    seen, out = set(), []
    for t in texts:
        if t['font'] == 0 and t['cls'] == 2 and in_scope(rects, t['x'], t['y'], tx, ty):
            s = t['text'].strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out
