import subprocess
import os

os.chdir('f:\\FnO')
print("Running Full January Backtest... This may take a minute.")
res = subprocess.run(['python', 'backend/scripts/backtest_jan.py'], capture_output=True, text=True, encoding='utf-8')
with open('january_full_audit.txt', 'w', encoding='ascii', errors='ignore') as f:
    f.write(res.stdout)
    f.write("\nERRORS:\n")
    f.write(res.stderr)
print("Backtest complete. Check january_full_audit.txt")
