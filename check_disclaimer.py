import os

files = [
    r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\frontend\index.html',
    r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\frontend\auth.html',
    r'C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\frontend\dashboard.html',
]

disclaimer = 'Decision-support tool, not financial advice. Signals and backtests do not guarantee future results.'

for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    has = disclaimer in content
    print(f'{os.path.basename(f)}: {"PASS" if has else "FAIL"}')