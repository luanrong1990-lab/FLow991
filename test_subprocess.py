import subprocess, sys, os
p = subprocess.Popen([sys.executable, '-m', 'agent.main'], cwd='d:/Flow')
p.wait()
