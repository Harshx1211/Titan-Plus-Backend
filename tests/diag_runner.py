import unittest
import sys
import os

# Absolute pathing for imports
current_dir = os.path.dirname(os.path.abspath(__file__)) # f:\FnO\tests
project_root = os.path.dirname(current_dir)             # f:\FnO
backend_dir = os.path.join(project_root, 'backend')

sys.path.append(project_root)
sys.path.append(backend_dir)

# Import the test class using full path if needed, or by appending tests dir
sys.path.append(current_dir)
import test_brain_v2

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(test_brain_v2.TestBrainV2)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        print("\n" + "!" * 40)
        print("DIAGNOSTIC FAILURE REPORT")
        print("!" * 40)
        for failure in result.failures:
            print(f"FAILURE in {failure[0]}:\n{failure[1]}")
        for error in result.errors:
            print(f"ERROR in {error[0]}:\n{error[1]}")
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)
