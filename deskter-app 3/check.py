"""Run all available automated checks without hiding earlier failures."""
import pathlib, shutil, subprocess, sys
ROOT=pathlib.Path(__file__).parent
commands=[[sys.executable,'-m','unittest','discover','-s','tests','-v']]
node=shutil.which('node')
if node:
    commands += [[node,'tests/'+name+'.cjs'] for name in ['pricing','ui','forms','network','account']]
else:
    print('Node.js is unavailable: frontend checks cannot run.',flush=True)
failed=not bool(node)
for command in commands:
    result=subprocess.run(command,cwd=ROOT)
    failed=failed or result.returncode!=0
print('Checks failed or were incomplete.' if failed else 'All configured automated checks passed. Browser acceptance remains separate.')
raise SystemExit(1 if failed else 0)
