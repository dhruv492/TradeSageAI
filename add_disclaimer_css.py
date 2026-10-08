path = r"C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\frontend\css\style.css"
with open(path, "r") as f:
    content = f.read()

new_class = "\n.persistent-disclaimer {\n  background: var(--bg-surface);\n  border-top: 1px solid var(--border-subtle);\n  border-bottom: 1px solid var(--border-subtle);\n  padding: 12px 20px;\n  font-size: 12px;\n  color: var(--text-dim);\n  text-align: center;\n  margin-top: 24px;\n  width: 100%;\n  box-sizing: border-box;\n}"

with open(path, "w") as f:
    f.write(content + new_class)
print("Added .persistent-disclaimer class")