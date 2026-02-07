# [v9.9.9] Notification Templates
# Using clean terminal-style layout

ENTRY_CARD = """
🚀 <b>TITAN ENTRY</b>

<b>Symbol</b>      : {symbol}
<b>Direction</b>   : {direction}
<b>Entry</b>       : ₹{entry_price:.2f}
<b>SL</b>          : ₹{stop_loss:.2f}
<b>Target</b>      : ₹{target:.2f}
<b>R:R</b>         : 1 : {risk_reward:.1f}

🧠 <b>Intelligence</b>
• {reasoning}
• Regime: {regime}

⚡ <b>Confidence: {confidence_pct}%</b>
"""

EXIT_CARD = """
🛡️ <b>TITAN EXIT</b>

<b>Reason</b>   : {reason}
<b>PnL</b>      : {pnl_sign}{pnl_pts:.2f} pts
<b>Duration</b> : {duration}m
<b>Peak</b>     : +{mfe:.2f} pts

📊 <b>Post Analysis</b>
• {exit_analysis}
"""

DAILY_GREETING = """
🌅 <b>Good Morning Harsh</b>

<i>"{wisdom}"</i>

<b>System Status:</b>
Signals Today : {signals_today}
Accuracy (7d) : {accuracy_7d}%
Equity Curve  : {equity_curve}
"""

EOD_SUMMARY = """
📈 <b>End of Day Report</b>

<b>Trades</b>    : {total_trades}
<b>Wins/Loss</b> : {wins}/{losses}
<b>Net PnL</b>   : {net_pnl_pts:+.2f} pts
<b>Max DD</b>    : {max_dd:.2f} pts

<b>Lesson:</b>
<i>"{lesson}"</i>
"""

MARKET_BLUEPRINT = """
🗺️ <b>INSTITUTIONAL MARKET BLUEPRINT</b>

<b>Index: {symbol}</b>
<b>Trend Expectation: {trend_bias}</b>

🛡️ <b>Support Ranges:</b>
{supports}

🚀 <b>Resistance Ranges:</b>
{resistances}

📊 <b>Strategic Note:</b>
<i>"{note}"</i>
"""
