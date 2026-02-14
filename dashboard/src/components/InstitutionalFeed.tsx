import { History as HistoryIcon } from 'lucide-react';
import { HistoricSignal } from '../types';

interface InstitutionalFeedProps {
    signals: HistoricSignal[];
}

export const InstitutionalFeed: React.FC<InstitutionalFeedProps> = ({ signals }) => {
    return (
        <section className="glass-panel rounded-3xl p-6 h-full font-sans">
            <div className="flex items-center justify-between mb-8">
                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Institutional Feed</h3>
                <HistoryIcon className="w-4 h-4 text-slate-600" />
            </div>

            <div className="space-y-6">
                {(signals.length > 0 ? signals : []).map((signal) => (
                    <div key={signal.id} className="relative pl-6 pb-6 border-l border-slate-800 last:border-0 hover:border-sky-500/30 transition-colors group">
                        <div className={`absolute left-[-5px] top-0 w-2.5 h-2.5 rounded-full ${signal.status === 'OPEN' ? 'bg-sky-500 shadow-[0_0_8px_#38bdf8]' : 'bg-slate-800'} group-hover:bg-sky-400 transition-colors`} />
                        <p className="text-[10px] text-slate-500 font-bold mb-1">
                            {new Date(signal.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                        <p className="text-xs font-bold text-white mb-1">{signal.symbol} Signal {signal.status === 'CLOSED' ? 'Completed' : 'Active'}</p>
                        <p className={`text-[10px] font-bold uppercase ${signal.pnl && signal.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {signal.pnl ? `${signal.pnl > 0 ? '+' : ''}${signal.pnl.toFixed(2)}R Realized` : `${signal.side} Strategy Engaged`}
                        </p>
                    </div>
                ))}
                {signals.length === 0 && (
                    <div className="text-center py-10">
                        <p className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">No Recent Signals</p>
                    </div>
                )}
            </div>

            <button className="w-full py-4 mt-4 bg-white/5 hover:bg-white/10 rounded-2xl text-[10px] font-bold uppercase tracking-widest text-slate-400 transition-all">
                Full History Report
            </button>
        </section>
    );
};
