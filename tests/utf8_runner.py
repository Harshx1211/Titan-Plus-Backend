import unittest
import sys
import os
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Absolute pathing for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
backend_dir = os.path.join(project_root, 'backend')
sys.path.append(project_root)
sys.path.append(backend_dir)
sys.path.append(current_dir)

import test_brain_v2

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(test_brain_v2.TestBrainV2)
    # Redirect stderr to stdout to capture everything
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        sys.exit(1)
    else:
        sys.exit(0)
