import sys
import os
# Add backend directory so conftest.py can find its parent
sys.path.insert(0, r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\backend')
sys.path.insert(0, r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\backend\tests')

import conftest

from tests.smoke_test_auth import test_auth_bypass_fix

print("Running auth smoke test...")
test_auth_bypass_fix()
print("Auth smoke test completed.")