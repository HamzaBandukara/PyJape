"""Kripke countermodels (Jape's "disproof" pane), against the REAL engine.
No GUI: checks that protocol.parse_transcript keeps the disproof pane apart
from the proof pane and decodes worlds, labels, tiles and forcing correctly."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jape import engine as E          # noqa: E402
from jape import protocol as P        # noqa: E402

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

def proof_texts(eng):
    return [t['text'] for t in eng.state().texts]

def formula(d, cls):
    return next(t for t in d['seq'] if t['font'] == 0 and t['cls'] == cls)


# ---- pure parser checks (no engine) ------------------------------------------
check(P.forcing_runs('\x01\x03\x14P\x15\x04∨\x01¬\x03\x14P\x15\x04\x02\x02') ==
      [('P', 'off'), ('∨¬', 'on'), ('P', 'off')],
      'forcing_runs colours each subformula by its innermost bracket (lock marks ignored)')
check(P.forcing_runs(' ⊧ ') == [(' ⊧ ', None)], 'forcing_runs leaves plain text uncoloured')
check(P.forcing_runs('\x03∃\x05x\x06.\x05\x05P\x06\x05(\x05x\x06)\x06\x06\x04') == [('∃x.P(x)', 'off')],
      'a quantifier body (not evaluated on its own) takes the colour of its formula')

t = '\n'.join([
    'OPENPROOF X 1', 'DRAWINPANE 0', 'DRAWSTRING 0 10 0 1 A',
    'SEQBOX 50 18 7', 'DRAWINPANE 1', 'DRAWSTRING 0 0 0 1 A', 'WORLDSSTART', 'WORLD 0 0 F',
    'CLEARPANE 1'])
st = P.parse_transcript(t)
check([x['text'] for x in st.texts] == ['A'] and st.disproof is None,
      'CLEARPANE 1 clears only the disproof, not the proof')
st = P.parse_transcript(t.replace('CLEARPANE 1', 'CLEARPANE 0'))
check(st.texts == [] and st.disproof and st.disproof['worlds'],
      'CLEARPANE 0 clears only the proof, not the disproof')

# ---- against the engine -------------------------------------------------------
eng = E.Engine(*E.default_paths()).start()
alerts = []
eng.on_alert = alerts.append

# 1. Propositional: ⊢ P∨¬P has a two-world countermodel.
prove(eng, 'P∨¬P')
before = proof_texts(eng)
eng.command('COMMAND disprove')
st = eng.state()
d = st.disproof
check(proof_texts(eng) == before,
      'disprove leaves the proof canvas alone (got %s)' % proof_texts(eng))
check(d is not None and [x['text'] for x in d['seq'] if x['font'] == 0] == [' ⊧ ', 'P∨¬P'],
      'the disproof pane holds the sequent " ⊧ P∨¬P"')
check(d['tiles'] == ['P'], 'tiles offered: %s' % d['tiles'])
check(list(d['worlds']) == [(0, 0)] and d['selected'] == [(0, 0)],
      'starts with one selected world at (0,0)')
c = formula(d, 1)
check(d['emph'].get((c['x'], c['y'])) is True and not P.is_countermodel(d),
      'with one empty world P∨¬P is forced, so not yet a countermodel')

eng.command('COMMAND addworld 0 0 0 60')
d = eng.state().disproof
check(d['worlds'][(0, 0)]['children'] == [(0, 60)],
      'addworld links a child world (child y > parent y)')
eng.command('COMMAND addworldlabel 0 60 P')
d = eng.state().disproof
check(d['worlds'][(0, 60)]['labels'] == [(False, 'P')], 'P labels the child world')
check(P.is_countermodel(d), 'root ⊮ P∨¬P once a later world forces P: a countermodel')
check(dict(P.forcing_runs(formula(d, 1)['raw'])).get('P∨¬P') == 'off',
      'the conclusion is drawn as not forced')

eng.command('COMMAND undo_disproof')
d = eng.state().disproof
check(d['worlds'][(0, 60)]['labels'] == [] and not P.is_countermodel(d),
      'undo_disproof takes the label away again')
eng.command('COMMAND redo_disproof')
check(P.is_countermodel(eng.state().disproof), 'redo_disproof puts it back')

# clicking a formula in the sequent colours the worlds by whether it holds there
eng.disproof_selection = ['%d %d' % (c['x'], c['y'])]
eng.command('COMMAND disproof_selection_change')
d = eng.state().disproof
check(d['seqsel'] == [(c['x'], c['y'])], 'the engine records the selected sequent formula')
check(d['worlds'][(0, 0)]['forced'] is False and d['worlds'][(0, 60)]['forced'] is True,
      'P∨¬P is tinted not-forced at the root and forced at the world above')
eng.disproof_selection = []
eng.command('COMMAND disproof_selection_change')
check(eng.state().disproof['seqsel'] == [], 'and the selection can be cleared again')

# disproving again would wipe the model: the engine asks, and Cancel keeps it
asked = []
eng.on_ask = lambda msg, buttons, default: asked.append((msg, buttons, default)) or 1
eng.command('COMMAND disprove')
eng.on_ask = None
check(asked and asked[0][1] == ['Wipe', 'Cancel'] and 'wipe' in asked[0][0].lower(),
      'disproving again asks before wiping the worlds (%s)' % (asked[:1],))
check(P.is_countermodel(eng.state().disproof), 'answering Cancel keeps the countermodel')

eng.command('COMMAND worldselect 0 60')
d = eng.state().disproof
check(d['selected'] == [(0, 60)] and not P.is_countermodel(d),
      'selecting the child world: P∨¬P is forced there, so no countermodel at that world')
eng.command('COMMAND worldselect 0 0')

eng.command('COMMAND done')
st = eng.state()
check(st.focus is None and P.open_windows(eng.lines) == {},
      'done on a countermodel closes the proof window (CLOSEPROOFS block)')
ent = next(e for e in st.panels['Conjectures'] if e['display'] == 'P∨¬P')
check(ent['disproved'] and not ent['proved'], 'the conjecture is marked disproved')

# the countermodel is saved with the proofs and comes back on reload
tmp = os.path.join(tempfile.mkdtemp(), 'disproof.jp')
check(eng.save_proofs(tmp), 'save_proofs writes a file')
with open(tmp, encoding='utf-8') as fh:
    saved = fh.read()
check('SEMANTICS' in saved and 'LABELS P' in saved,
      'the saved file contains the countermodel (SEMANTICS … WORLD … LABELS P)')
eng2 = E.Engine(*E.default_paths()).start()
eng2.load_proofs(tmp)
ent2 = [e for e in eng2.state().panels.get('Conjectures', []) if e['display'] == 'P∨¬P']
check(ent2 and ent2[-1]['disproved'], 'reloading restores the disproved mark')
eng2.stop()

# 2. A selection in the proof still refers to the proof pane while a disproof is open.
prove(eng, 'P→Q ⊢ Q→P')
eng.command('COMMAND disprove')
st = eng.state()
g = [x for x in st.texts if x['text'] == 'Q→P']
check(len(g) == 1, 'proof canvas shows Q→P once, not again from the disproof pane')
rule = next(i['command'] for m in st.menus.values() for i in m if i['label'].startswith('→ intro'))
alerts.clear()
eng.selection = ['%d %d 1' % (g[0]['x'], g[0]['y'])]
eng.command('COMMAND ' + rule)
eng.selection = []
check(not any('catastroph' in a for a in alerts) and 'assumption' in proof_texts(eng),
      'a proof step still works with the disproof open (alerts: %s)' % alerts)
check(eng.state().disproof is not None, 'and the disproof survives the proof step')

# 3. Predicate logic: ∃x.P(x) ⊢ ∀x.P(x).
prove(eng, '∃x.P(x) ⊢ ∀x.P(x)')
eng.command('COMMAND disprove')
d = eng.state().disproof
check(sorted(d['tiles']) == ['P(i)', 'actual i'], 'first-order tiles: %s' % d['tiles'])
for lab in ('"actual i"', '"actual j"', 'P(i)'):
    eng.command('COMMAND addworldlabel 0 0 ' + lab)
d = eng.state().disproof
check([l for _, l in d['worlds'][(0, 0)]['labels']] == ['actual i', 'actual j', 'P(i)'],
      'a world holds individuals and atomic facts, including untiled ones (actual j)')
check(P.is_countermodel(d), 'P(i) but not P(j): ∃x.P(x) forced, ∀x.P(x) not')

# 4. "Start again" / "Close": the engine can't drop a countermodel, but disproving
#    again and answering Wipe resets it to one blank world, and Undo restores it.
check(not P.is_blank(d), 'a model with labels is not blank')
eng.on_ask = lambda msg, buttons, default: 0          # Wipe
eng.command('COMMAND disprove')
eng.on_ask = None
d = eng.state().disproof
check(P.is_blank(d), 'disprove + Wipe leaves one blank world (what Close/Start again use)')
eng.command('COMMAND undo_disproof')
check(P.is_countermodel(eng.state().disproof), 'and undo_disproof brings the old model back')

eng.stop()
print('\n%d passed, %d failed' % (passed, failed))
sys.exit(1 if failed else 0)
