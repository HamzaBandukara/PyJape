"""Does the engine's own save/reload work over our bridge? Save a conjecture
(+ its proof) to a .jp file, start a FRESH engine, reload the file, and check
the conjecture comes back — and whether the proof comes with it."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jape import engine as E  # noqa: E402
from jape import protocol as P  # noqa: E402
from jape import logic as L  # noqa: E402

passed = failed = 0
def check(c, m):
    global passed, failed
    print(("ok   " if c else "XX   ") + m); passed += bool(c); failed += (not c)

def menu_cmd(state, menu, pat):
    for it in state.menus.get(menu, []):
        if re.search(pat, it['label']):
            return it['command']

def all_panel_displays(state):
    out = []
    for p, es in state.panels.items():
        for e in es:
            out.append((p, e['display']))
    return out

engine_path, entry = E.default_paths()
savefile = os.path.join(tempfile.gettempdir(), 'jape_save_test.jp')
if os.path.exists(savefile):
    os.remove(savefile)

# --- session 1: add a conjecture, prove it, save ----------------------------
eng = E.Engine(engine_path, entry); eng.start()
eng.command('COMMAND addnewconjecture Conjectures A → A')
st = eng.state()
cmd = P.conjecture_command(st, st.selected['panel'], st.selected['name']) if st.selected else None
eng.command('COMMAND proveconjecture ' + cmd)
st = eng.state()
check(st.proof_title is not None, "session1: proof A → A opened")
# prove it: → intro (makes assumption), then hyp
intro = menu_cmd(st, 'Backward', r'→ intro')
eng.command('COMMAND ' + intro)
st = eng.state()
hyp = menu_cmd(st, 'Backward', r'^hyp')
eng.command('COMMAND ' + hyp)
st = eng.state()
proved = ('¬ elim' not in '') and any(t['text'] == 'A' for t in st.texts)
check(True, "session1: applied → intro + hyp (proof attempt)")

ok = eng.save_proofs(savefile)
check(ok, f"session1: saveproofs wrote {savefile} (exists={os.path.exists(savefile)})")
if os.path.exists(savefile):
    content = open(savefile, encoding='utf-8', errors='replace').read()
    check('A' in content, "saved file is non-empty and mentions the conjecture")
    print("---- saved file (first 500 chars) ----")
    print(content[:500])
    print("--------------------------------------")
eng.stop()

# --- session 2: fresh engine, reload ----------------------------------------
eng2 = E.Engine(engine_path, entry); eng2.start()
before = set(all_panel_displays(eng2.state()))
loaded = eng2.load_proofs(savefile)
check(loaded, "session2: use <savefile> ran")
after = all_panel_displays(eng2.state())
new_entries = [d for d in after if d not in before]
check(any('A' in d for (_p, d) in after), f"session2: conjecture present after reload (new={new_entries})")
# is the proof restored? proveconjecture it and see if it's already done
st2 = eng2.state()
# find the reloaded conjecture command in any panel
target = None
for p, es in st2.panels.items():
    for e in es:
        if e['display'].replace(' ', '') == 'A→A':
            target = e['command']
if target:
    eng2.command('COMMAND proveconjecture ' + target)
    st2 = eng2.state()
    # a saved+proved theorem reopens as already proved (no "..." gaps); heuristic:
    dots = any('. . .' in t['text'] or t['text'] == '...' for t in st2.texts if t['font'] == 1)
    print("reopened proof has open gaps (unproved)?", dots)
    check(L.is_complete(st2.texts), "reopened saved proof comes back complete")

    # Restart (app.restart_proof): a loaded proof has no engine edit-history, so
    # undo/backtrack do nothing — restart must prune the root goal instead. This
    # guards the regression where "Restart proof" silently did nothing on a
    # proof opened from a file.
    import re as _re
    for cmd in ('undo_proof', 'backtrack'):               # history-based: no-ops here
        eng2.command('COMMAND ' + cmd)
    check(L.is_complete(eng2.state().texts),
          "undo/backtrack can't reset a loaded proof (no history) — still complete")
    concl = [t for t in st2.texts if t['font'] == 0 and t['cls'] == 1]
    root = max(concl, key=lambda t: t['y'])
    eng2.selection = ['%d %d 1' % (root['x'], root['y'])]
    eng2.command('COMMAND prune'); eng2.selection = []
    st2 = eng2.state()
    check(not L.is_complete(st2.texts) and L.open_goals(st2.texts),
          "restart (prune root) resets the loaded proof back to its open goal")
eng2.stop()

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
