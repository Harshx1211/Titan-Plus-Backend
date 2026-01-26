import logging
import pandas as pd
from datetime import datetime, time
from typing import Dict, List
from supabase_manager import SupabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("session_auditor")

class SessionAuditor:
    """
    Electronic Auditor for Titan Plus.
    Calculates Daily Expectancy, Win Rate, and Alpha Persistence.
    Ensures total accountability during the 20-session lock.
    """
    def __init__(self):
        self.db = SupabaseManager()

    def generate_daily_report(self, date_str: str = None) -> Dict:
        """
        Generates a performance audit for a specific date.
        Format: YYYY-MM-DD
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"AUDITOR: Generating report for {date_str}")
        
        # 1. Fetch History
        history = self.db.get_history(limit=200)
        if not history:
            return {"date": date_str, "status": "NO_DATA"}

        df = pd.DataFrame(history)
        
        # 2. Filter for specific date
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        session_df = df[df['timestamp'].dt.strftime('%Y-%m-%d') == date_str]
        
        if session_df.empty:
            return {"date": date_str, "status": "SESSION_EMPTY"}

        # 3. Calculate Core Metrics
        outcomes = session_df[session_df['state'] == 'OUTCOME']
        intents = session_df[session_df['state'] == 'INTENT']
        
        wins = len(outcomes[outcomes['value'] == 'WIN'])
        losses = len(outcomes[outcomes['value'] == 'LOSS'])
        total_resolved = wins + losses
        win_rate = (wins / total_resolved * 100) if total_resolved > 0 else 0.0

        # 4. Persistence Audit (Structural vs Tactical Alpha)
        structural_wins = len(outcomes[(outcomes['value'] == 'WIN') & (outcomes.get('persistence', False) == True)])
        persistence_ratio = (structural_wins / wins * 100) if wins > 0 else 0.0

        # 5. Expectancy (Assuming 1:2.5 Risk-Reward standard)
        # R = Risk element. Loss = -1R, Win = +2.5R
        expectancy = (wins * 2.5) - (losses * 1.0)

        report = {
            "date": date_str,
            "metrics": {
                "total_signals": len(intents),
                "resolved_trades": total_resolved,
                "wins": wins,
                "losses": losses,
                "win_rate": f"{win_rate:.2f}%",
                "expectancy_r": f"{expectancy:+.2f}R",
                "persistence_ratio": f"{persistence_ratio:.1f}%"
            },
            "verdict": "POSITIVE" if expectancy > 0 else "NEGATIVE" if expectancy < 0 else "NEUTRAL",
            "accountability_status": "VERIFIED" if total_resolved > 0 else "OVERSIGHT_PENDING"
        }

        logger.info(f"AUDITOR: Report Complete. Verdict: {report['verdict']}")
        return report

    def get_session_summary_text(self, date_str: str = None) -> str:
        report = self.generate_daily_report(date_str)
        if report.get("status"):
            return f"AUDIT: No data found for {report['date']}."
        
        m = report['metrics']
        return (
            f"--- INSTITUTIONAL SESSION AUDIT [{report['date']}] ---\n"
            f"Signals: {m['total_signals']} | Resolved: {m['resolved_trades']}\n"
            f"Win Rate: {m['win_rate']} | Expectancy: {m['expectancy_r']}\n"
            f"Structural Persistence: {m['persistence_ratio']}\n"
            f"VERDICT: {report['verdict']}\n"
            f"-------------------------------------------"
        )

if __name__ == "__main__":
    auditor = SessionAuditor()
    print(auditor.get_session_summary_text())
