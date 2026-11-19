"""Regression: the app must work when installed under a path WITH SPACES
(e.g. C:\\Program Files\\PyJape). The initial `use` of the theory must be
quoted, or the theory never loads (empty Exercises, Prove does nothing)."""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jape import engine as E
from jape import protocol as P

src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')
base = os.path.join(tempfile.gettempdir(), 'Spaced Dir', 'PyJape', 'resources')
if os.path.exists(os.path.dirname(os.path.dirname(base))):
    shutil.rmtree(os.path.dirname(os.path.dirname(base)))
os.makedirs(base)
shutil.copy2(os.path.join(src, E.ENGINE_NAME), os.path.join(base, E.ENGINE_NAME))
os.chmod(os.path.join(base, E.ENGINE_NAME), 0o755)
shutil.copytree(os.path.join(src, 'examples'), os.path.join(base, 'examples'))

engine = os.path.join(base, E.ENGINE_NAME)
entry = os.path.join(base, 'examples', 'natural_deduction', 'I2L.jt')
assert ' ' in entry, 'test path should contain a space'

eng = E.Engine(engine, entry)
eng.start()
st = eng.state()
ok_theory = len(st.menus) > 0 and 'Conjectures' in st.panels
eng.command('COMMAND addnewconjecture Saved A \u2192 A')
st = eng.state()
cmd = P.conjecture_command(st, st.selected['panel'], st.selected['name']) if st.selected else None
eng.command('COMMAND proveconjecture ' + cmd)
st = eng.state()
ok_prove = st.proof_title is not None
eng.stop()
shutil.rmtree(os.path.dirname(os.path.dirname(base)))

print('theory loaded under spaced path:', ok_theory)
print('Prove works under spaced path  :', ok_prove)
print('RESULT:', 'PASS' if (ok_theory and ok_prove) else 'FAIL')
sys.exit(0 if (ok_theory and ok_prove) else 1)
