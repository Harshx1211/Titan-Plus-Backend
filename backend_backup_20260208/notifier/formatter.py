# [v9.9.9] Notifier Formatter
from .templates import ENTRY_CARD, EXIT_CARD, DAILY_GREETING, EOD_SUMMARY

class NotifierFormatter:
    @staticmethod
    def format_entry(signal: dict) -> str:
        rr = abs(signal['target'] - signal['entry_price']) / abs(signal['entry_price'] - signal['stop_loss']) if abs(signal['entry_price'] - signal['stop_loss']) > 0 else 1.0
        return ENTRY_CARD.format(
            symbol=signal.get('symbol', 'NIFTY'),
            direction="🟢 LONG" if "BULLISH" in signal.get('reasoning', '') else "🔴 SHORT",
            entry_price=signal.get('entry_price', 0.0),
            stop_loss=signal.get('stop_loss', 0.0),
            target=signal.get('target', 0.0),
            risk_reward=rr,
            reasoning=signal.get('reasoning', 'Algorithmic Confluence'),
            regime=signal.get('regime', 'TREND'),
            confidence_pct=int(signal.get('score', 0.85) * 100)
        )

    @staticmethod
    def format_exit(signal_data: dict, reason: str, exit_analysis: str) -> str:
        pnl = signal_data.get('pnl', 0.0)
        return EXIT_CARD.format(
            reason=reason,
            pnl_sign="+" if pnl >= 0 else "",
            pnl_pts=pnl,
            duration=signal_data.get('duration_min', 0),
            mfe=signal_data.get('mfe', 0.0),
            exit_analysis=exit_analysis
        )

    @staticmethod
    def format_greeting(stats: dict, wisdom: str) -> str:
        return DAILY_GREETING.format(
            wisdom=wisdom,
            signals_today=stats.get('signals_today', 0),
            accuracy_7d=stats.get('accuracy_7d', 0),
            equity_curve=stats.get('equity_curve', 'STABLE')
        )

    @staticmethod
    def format_blueprint(symbol: str, trend: str, supports: list, resistances: list, note: str) -> str:
        from .templates import MARKET_BLUEPRINT
        s_text = "\n".join([f"• ₹{s:,.0f}" for s in supports[:4]]) if supports else "• Calculating..."
        r_text = "\n".join([f"• ₹{r:,.0f}" for r in resistances[:4]]) if resistances else "• Calculating..."
        return MARKET_BLUEPRINT.format(
            symbol=symbol,
            trend_bias=trend,
            supports=s_text,
            resistances=r_text,
            note=note
        )
