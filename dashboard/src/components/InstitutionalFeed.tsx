import React from 'react';
import { History as HistoryIcon, Clock, ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';
import { HistoricSignal } from '../types';

interface InstitutionalFeedProps {
    signals: HistoricSignal[];
}

export const InstitutionalFeed: React.FC<InstitutionalFeedProps> = ({ signals }) => {
    const sortedSignals = [...(signals || [])].sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    return (
        <section className="glass-panel rounded-[2rem] p-8 h-full font-sans flex flex-col border border-white/5 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-[0.02] pointer-events-none">
                <HistoryIcon size={120} />
            </div>

            <div className="flex items-center justify-between mb-8 relative z-10">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-sky-500/10 flex items-center justify-center text-sky-400">
                        <Activity size={16} />
                    </div>
                    <div>
                        <h3 className="text-xs font-black uppercase tracking-[0.2em] text-white">Execution Ledger</h3>
                        <p className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Live Institutional Stream</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/5 rounded-full border border-emerald-500/10">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-[9px] font-black text-emerald-500/80 uppercase tracking-widest">Synced</span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 scrollbar-hide pr-1 relative z-10">
                {sortedSignals.map((signal) => (
                    <div
                        key={signal.id}
                        className="p-5 bg-white/[0.02] hover:bg-white/[0.05] rounded-2xl border border-white/5 hover:border-sky-500/20 transition-all group cursor-default"
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center gap-4">
                                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${signal.side === 'LONG' ? 'bg-emerald-500/10 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.1)]' : 'bg-rose-500/10 text-rose-400 shadow-[0_0_15px_rgba(239,68,68,0.1)]'}`}>
                                    {signal.side === 'LONG' ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
                                </div>
                                <div>
                                    <p className="text-sm font-black text-white tracking-tight underline decoration-sky-500/30 underline-offset-4">{signal.symbol}</p>
                                    <div className="flex items-center gap-2 mt-1">
                                        <Clock size={10} className="text-slate-600" />
                                        <p className="text-[9px] text-slate-500 font-black uppercase tracking-widest">
                                            {new Date(signal.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                        </p>
                                    </div>
                                </div>
                            </div>
                            <div className={`px-3 py-1 rounded-md text-[9px] font-black tracking-widest uppercase ${signal.status === 'OPEN' ? 'bg-sky-500 text-white shadow-[0_0_15px_rgba(56,189,248,0.3)]' : 'bg-slate-800 text-slate-500'}`}>
                                {signal.status}
                            </div>
                        </div>

                        <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/5">
                            <div className="flex flex-col gap-1">
                                <span className="text-[9px] text-slate-500 font-black uppercase tracking-widest">Entry Benchmark</span>
                                <span className="text-xs text-white font-mono font-black italic">₹{(Number(signal.entry_price || 0) * 83).toLocaleString()}</span>
                            </div>
                            <div className="text-right flex flex-col gap-1">
                                <span className="text-[9px] text-slate-500 font-black uppercase tracking-widest">P&L Attribution</span>
                                <p className={`text-xs font-black font-mono ${signal.pnl && signal.pnl >= 0 ? 'text-emerald-400' : 'text-slate-600'}`}>
                                    {signal.pnl ? `${signal.pnl > 0 ? '+' : ''}${signal.pnl.toFixed(2)}R` : 'TRACKING...'}
                                </p>
                            </div>
                        </div>
                    </div>
                ))}

                {sortedSignals.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-24 opacity-20 group">
                        <div className="w-16 h-16 rounded-full bg-slate-900 flex items-center justify-center mb-6 border border-slate-800 group-hover:border-sky-500 transition-all duration-500">
                            <HistoryIcon size={32} className="text-slate-600" />
                        </div>
                        <p className="text-[10px] text-slate-600 font-black uppercase tracking-[0.4em]">No Active Log Found</p>
                    </div>
                )}
            </div>

            <button className="w-full py-5 mt-6 bg-white/5 hover:bg-sky-500/10 border border-white/5 hover:border-sky-500/30 rounded-2xl text-[10px] font-black uppercase tracking-[0.3em] text-slate-400 hover:text-sky-400 transition-all active:scale-[0.98] group flex items-center justify-center gap-3">
                <HistoryIcon size={14} className="group-hover:rotate-12 transition-transform" />
                Access Full Execution Archives
            </button>
        </section>
    );
};
