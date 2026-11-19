"""Box-scope of the "What we know" panel, against the REAL engine. A hypothesis
in a box that has closed (a sibling or finished sub-proof) must NOT be reported
as known at the line being worked on. No GUI — logic.facts_in_scope is pure."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jape import engine as E          # noqa: E402
from jape import protocol as P        # noqa: E402
from jape import logic as L           # noqa: E402

passed = failed = 0
def check(cond, msg):
    global passed, failed
    print(("ok   " if cond else "XX   ") + msg)
    passed += bool(cond); failed += (not cond)

def prove(eng, conj):
    eng.command('COMMAND addnewconjecture Conjectures ' + conj)
    st = eng.state()
    eng.command('COMMAND proveconjecture ' +
                P.conjecture_command(st, st.selected['panel'], st.selected['name']))

def menu_cmd(state, menu, pattern):
    import re
    for it in state.menus.get(menu, []):
        if re.search(pattern, it['label']):
            return it['command']
    return None

engine_path, entry = E.default_paths()
eng = E.Engine(engine_path, entry); eng.start()

# === sibling boxes: E∨F ⊢ F∨E via forward ∨ elim ===========================
prove(eng, 'E∨F ⊢ F∨E')
st = eng.state()
h = [t for t in st.texts if t['font'] == 0 and t['cls'] == 2 and t['text'] == 'E∨F'][0]
eng.selection = ['%d %d 2' % (h['x'], h['y'])]
eng.command('COMMAND apply (Forward (QUOTE(_A∨_B)) '
            '(Noarg("targeted forward"(ForwardUncut 0 "∨ elim")"∨ elim")"∨ elim") '
            '"∨ elim" "∨ intro" "A∨B")')
eng.selection = []
st = eng.state()

opens = sorted(L.open_goals(st.texts), key=lambda t: t['y'])
check(len(opens) == 2, "∨ elim opened two sibling sub-proofs (%d open goals)" % len(opens))
boxA, boxB = opens[0], opens[1]          # E-assumption box (top), F-assumption box

fa = L.facts_in_scope(st.texts, st.rects, [{'x': boxA['x'], 'y': boxA['y'], 'cls': 1}])
check(set(fa) == {'E∨F', 'E'}, "in the E box, known = {E∨F, E}, not F  (got %s)" % fa)
check('F' not in fa, "the sibling F box is NOT in scope in the E box")

fb = L.facts_in_scope(st.texts, st.rects, [{'x': boxB['x'], 'y': boxB['y'], 'cls': 1}])
check(set(fb) == {'E∨F', 'F'}, "in the F box, known = {E∨F, F}, not E  (got %s)" % fb)

# no selection -> defaults to the first (top) open goal = the E box
fdef = L.facts_in_scope(st.texts, st.rects, [])
check(set(fdef) == {'E∨F', 'E'}, "no selection falls back to the first open goal (got %s)" % fdef)

# active-case labelling: names which of the two open scopes is shown
check(L.active_case(st.texts, st.rects, []) == ('F∨E', 1, 2),
      "no selection -> 'case 1 of 2' (got %s)" % (L.active_case(st.texts, st.rects, []),))
selB = [{'x': boxB['x'], 'y': boxB['y'], 'cls': 1}]
check(L.active_case(st.texts, st.rects, selB) == ('F∨E', 2, 2),
      "selecting the F box -> 'case 2 of 2' (got %s)" % (L.active_case(st.texts, st.rects, selB),))

# === nested boxes + completion: E → (F → E) ================================
IMP = ('apply (BackwardOnlyA (QUOTE(_A→_B)) (Noarg "→ intro" "→ intro") '
       '"→ intro" "A→B")')
prove(eng, 'E → (F → E)')
for formula in ('E→(F→E)', 'F→E'):               # two backward → intros
    st = eng.state()
    g = [t for t in st.texts if t['font'] == 0 and t['cls'] == 1 and t['text'] == formula][0]
    eng.selection = ['%d %d 1' % (g['x'], g['y'])]
    eng.command('COMMAND ' + IMP); eng.selection = []
st = eng.state()
check(L.is_complete(st.texts), "E → (F → E) is complete after two → intros")
# finished, no premises -> nothing is globally known
check(L.facts_in_scope(st.texts, st.rects, []) == [],
      "a finished premise-free proof reports no known facts")

# === completion WITH a premise: ¬¬E ⊢ E (contra + forward ¬ elim) ==========
prove(eng, '¬¬E ⊢ E')
st = eng.state()
eng.command('COMMAND ' + menu_cmd(st, 'Backward', r'contra \(classical'))   # assumes ¬E, goal ⊥
st = eng.state()
sel = {t['text']: t for t in st.texts if t['font'] == 0 and t['cls'] == 2}
eng.selection = ['%d %d 2' % (sel['¬E']['x'], sel['¬E']['y']),
                 '%d %d 2' % (sel['¬¬E']['x'], sel['¬¬E']['y'])]
eng.command('COMMAND ' + menu_cmd(st, 'Forward', r'^¬ elim')); eng.selection = []
st = eng.state()
check(L.is_complete(st.texts), "¬¬E ⊢ E complete after contra + ¬ elim")
# ¬E lived in the contra box, which has now closed -> only the premise ¬¬E is known
fin = L.facts_in_scope(st.texts, st.rects, [])
check(fin == ['¬¬E'], "finished proof shows only the premise ¬¬E, not the discharged ¬E (got %s)" % fin)

eng.stop()
print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
