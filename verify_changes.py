import sys
sys.path.insert(0, r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\backend')

import ast

# Check app.py syntax and key features
path = r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\backend\app.py'
with open(path, 'r') as f:
    content = f.read()

try:
    ast.parse(content)
    print("app.py syntax: OK")
except SyntaxError as e:
    print(f"app.py syntax: FAIL - {e}")

checks = [
    ('FLASK_DEBUG env', 'os.environ.get("FLASK_DEBUG") == "1"' in content),
    ('SECRET_KEY raise', 'raise ValueError' in content and 'SECRET_KEY' in content),
    ('SEED_DEMO_USER', 'SEED_DEMO_USER' in content),
    ('debug=os.environ', 'debug=os.environ' in content),
]

for name, result in checks:
    status = "PASS" if result else "FAIL"
    print(f'{name}: {status}')