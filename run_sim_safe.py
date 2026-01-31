import subprocess
import os

os.chdir('f:\\FnO')
res = subprocess.run(['python', 'backend/scripts/simulate_last_day.py'], capture_output=True, text=True, encoding='utf-8')
with open('simulation_final.txt', 'w', encoding='ascii', errors='ignore') as f:
    f.write(res.stdout)
    f.write("\nERRORS:\n")
    f.write(res.stderr)
print("Simulation complete. Check simulation_final.txt")
