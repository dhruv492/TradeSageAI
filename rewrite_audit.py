path = r"C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI\frontend\js\app.js"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the section to replace: from "// Render plain-English summary card" to 
# just before "// Render table rows"
start_marker = "// Render plain-English summary card"
end_marker = "// Render table rows"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx >= 0 and end_idx > start_idx:
    # Get the replacement text
    replacement = """    // Render plain-English summary card
    const summaryCard = document.getElementById("auditSummaryCard");
    if (summaryCard) {
      let gradeText = "⚪ VERIFICATION PENDING";
      let gradeColor = "var(--text-dim)";
      let gradeBg = "rgba(148,163,184,0.12)";
      let plainText = `Predictions for <strong>${this._currentSymbol}</strong> have been recorded, but subsequent market price candles are still unfolding to verify directional ground truth.`;

      if (resolvedAll.length > 0) {
        // Neutral wording: hit rate with sample size, no "reliably", "strong", "proven"
        const hitRateLabel = `${overallAcc.toFixed(1)}%`;
        if (overallAcc >= 70) {
          gradeText = "🟢 CONFIRMED HIT RATE";
          gradeColor = "var(--fin-pos)";
          gradeBg = "rgba(16,185,129,0.12)";
          plainText = `Of <strong>${resolvedAll.length}</strong> resolved forecasts for <strong>${this._currentSymbol}</strong>, <strong>${hitRateLabel}</strong> matched the realised direction. Small samples are unreliable and past results do not predict future ones.`;
        } else if (overallAcc >= 50) {
          gradeText = "🟡 MODERATE HIT RATE";
          gradeColor = "var(--fin-alert)";
          gradeBg = "rgba(245,158,11,0.12)";
          plainText = `Of <strong>${resolvedAll.length}</strong> resolved forecasts for <strong>${this._currentSymbol}</strong>, <strong>${hitRateLabel}</strong> matched the realised direction. Use with confirming technical indicators; no guarantee of future direction.`;
        } else {
          gradeText = "🔴 INSUFFICIENT HIT RATE";
          gradeColor = "var(--fin-neg)";
          gradeBg = "rgba(239,68,68,0.12)";
          plainText = `Of <strong>${resolvedAll.length}</strong> resolved forecasts for <strong>${this._currentSymbol}</strong>, <strong>${hitRateLabel}</strong> matched the realised direction. High volatility or regime shifts caused repeated forecast misses; past performance does not guarantee future results.`;
        }
      }

      summaryCard.innerHTML = `
        <div class="audit-summary-box">
          <div class="audit-summary-header">
            <div>
              <span style="font-size: 13px; font-weight: 700; color: var(--text-main); text-transform: uppercase; letter-spacing: 0.04em;">
                Empirical Model Audit: ${this._currentSymbol}
              </span>
            </div>
            <span class="audit-grade-pill" style="color: ${gradeColor}; background: ${gradeBg}; border: 1px solid ${gradeColor}40;">
              ${gradeText}
            </span>
          </div>

          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.5; margin: 0 0 10px;">
            ${plainText}
          </p>

          <div class="audit-grid">
            <div class="audit-tile">
              <div class="audit-tile-lbl">Hit rate (n = X)</div>
              <div class="audit-tile-val mono ${overallAcc !== null && overallAcc >= 60 ? 'val-pos' : (overallAcc !== null && overallAcc < 50 ? 'val-neg' : 'val-neu')}">
                ${overallAcc !== null ? `${overallAcc.toFixed(1)}% (n = ${resolvedAll.length})` : 'Pending'}
              </div>
            </div>
            <div class="audit-tile">
              <div class="audit-tile-lbl">Resolved / Total</div>
              <div class="audit-tile-val mono">${resolvedAll.length} / ${rawData.length}</div>
            </div>
            <div class="audit-tile">
              <div class="audit-tile-lbl">Random Forest</div>
              <div class="audit-tile-val mono ${rfAcc !== null && rfAcc >= 60 ? 'val-pos' : ''}">
                ${rfAcc !== null ? `${rfAcc.toFixed(1)}% (n = ${rfResolved.length})` : '—'}
              </div>
            </div>
            <div class="audit-tile">
              <div class="audit-tile-lbl">Shallow LSTM</div>
              <div class="audit-tile-val mono ${lstmAcc !== null && lstmAcc >= 60 ? 'val-pos' : ''}>
                ${lstmAcc !== null ? `${lstmAcc.toFixed(1)}% (n = ${lstmResolved.length})` : '—'}
              </div>
            </div>
          </div>
        </div>
      `;
      summaryCard.style.display = "block";
    }

    // Render table rows
    const tbody = document.getElementById("tbl-history-body");
    if (!tbody) return;"""

    new_content = content[:start_idx] + replacement + content[end_idx:]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Replacement done successfully")
else:
    print(f"Could not find markers: start={start_idx}, end={end_idx}")