"""Headless proof of the Python bridge against the REAL engine: drive the
¬¬E ⊢ E proof (contra + multi-select forward ¬ elim), test undo, and the
"what we know" fact extraction. No GUI, no tkinter — just the pipe."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jape import engine as E          # noqa: E402
from jape import protocol as P        # noqa: E402

passed = failed = 0
def check(cond, msg):
    global passed, failed
    print(("ok   " if cond else "XX   ") + msg)
    passed += bool(cond); failed += (not cond)

def menu_cmd(state, menu, pattern):
    for it in state.menus.get(menu, []):
        if re.search(pattern, it['label']):
            return it['command']
    return None

def hyps(state):
    return [t for t in state.texts if t['font'] == 0 and t['cls'] == 2]

def annotations(state):
    return ''.join(t['text'] for t in state.texts if t['font'] == 1)


engine_path, entry = E.default_paths()
eng = E.Engine(engine_path, entry)
eng.start()
st = eng.state()
check(len(st.menus) > 0, "theory loaded (menus present) after start")

# --- open ¬¬E ⊢ E via the two-phase new-exercise flow -----------------------
eng.command('COMMAND addnewconjecture Conjectures ¬¬E ⊢ E')
st = eng.state()
check(st.selected is not None, "addnewconjecture emitted SELECTPANELENTRY")
cmd = P.conjecture_command(st, st.selected['panel'], st.selected['name']) if st.selected else None
eng.command('COMMAND proveconjecture ' + cmd)
st = eng.state()
check(st.proof_title == '¬¬E ⊢ E', f"proof opened (title={st.proof_title!r})")

# --- backward: contra (classical) -------------------------------------------
contra = menu_cmd(st, 'Backward', r'contra \(classical')
eng.command('COMMAND ' + contra)
st = eng.state()
hyp_texts = sorted(h['text'] for h in hyps(st))
check(hyp_texts == ['¬E', '¬¬E'], f"after contra, hyps = {hyp_texts}")

# --- select both hypotheses, then forward ¬ elim ----------------------------
sel = {h['text']: h for h in hyps(st)}
eng.selection = [f"{sel['¬E']['x']} {sel['¬E']['y']} 2",
                 f"{sel['¬¬E']['x']} {sel['¬¬E']['y']} 2"]
elim = menu_cmd(st, 'Forward', r'^¬ elim')
eng.command('COMMAND ' + elim)
eng.selection = []
st = eng.state()
ann = annotations(st)
check('¬ elim' in ann, f"forward ¬ elim applied (annotations contain '¬ elim')")
check(st.alert is None or 'elim' not in (st.alert or ''), "no selection error on ¬ elim")

# --- undo the last step (no selection needed) -------------------------------
eng.command('COMMAND undo_proof')
st = eng.state()
check('¬ elim' not in annotations(st), "undo_proof removed the ¬ elim step")

# --- "what we know": hyps in scope are the known facts ----------------------
facts = sorted({h['text'] for h in hyps(st)})
check('¬¬E' in facts, f"known facts include the premise ¬¬E (facts={facts})")

eng.stop()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
