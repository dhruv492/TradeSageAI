path = r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\.env.example'
with open(path, 'r') as f:
    content = f.read()
checks = ['FLASK_DEBUG', 'SEED_DEMO_USER']
for c in checks:
    result = c in content
    print(f'{c}: {"PASS" if result else "FAIL"}')