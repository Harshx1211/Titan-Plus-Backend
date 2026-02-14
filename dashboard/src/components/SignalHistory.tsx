import React from 'react';
import { motion } from 'framer-motion';
import { History, TrendingUp, TrendingDown, Check, X } from 'lucide-react';
import { HistoricSignal } from '../types';

interface SignalHistoryProps {
    signals: HistoricSignal[];
}

export const SignalHistory: React.FC<SignalHistoryProps> = ({ signals }) => {
    return (
        <div className="glass-card rounded-xl p-5 h-[620px] flex flex-col">
            <div className="flex items-center gap-2 mb-4">
                <History className="w-5 h-5 text-blue-400" />
                <h2 className="text-lg font-bold text-slate-100">Signal History</h2>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 scrollbar-hide">
                {signals.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center text-slate-600">
                            <History className="w-12 h-12 mx-auto mb-2 opacity-30" />
                            <p className="text-sm">No signals yet</p>
                            <p className="text-xs mt-1">Waiting for setup...</p>
                        </div>
                    </div>
                ) : (
                    signals.map((signal, index) => {
                        const isBullish = signal.side === 'LONG';
                        const isWin = signal.pnl && signal.pnl > 0;
                        const isLoss = signal.pnl && signal.pnl < 0;
                        const isClosed = signal.status === 'CLOSED';

                        return (
                            <motion.div
                                key={signal.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.05 }}
                                className={`p-4 rounded-lg border transition-all ${isClosed
                                        ? isWin
                                            ? 'bg-emerald-500/5 border-emerald-500/30 hover:bg-emerald-500/10'
                                            : isLoss
                                                ? 'bg-red-500/5 border-red-500/30 hover:bg-red-500/10'
                                                : 'bg-slate-800/30 border-slate-700/30 hover:bg-slate-800/50'
                                        : 'bg-blue-500/5 border-blue-500/30 hover:bg-blue-500/10'
                                    }`}
                            >
                                {/* Header */}
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-bold text-white">
                                            {signal.symbol}
                                        </span>
                                        <div className={`px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1 ${isBullish
                                                ? 'bg-emerald-500/20 text-emerald-400'
                                                : 'bg-red-500/20 text-red-400'
                                            }`}>
                                            {isBullish ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                            {signal.side}
                                        </div>
                                    </div>

                                    {isClosed && (
                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${isWin ? 'bg-emerald-500/20' : isLoss ? 'bg-red-500/20' : 'bg-slate-700/20'
                                            }`}>
                                            {isWin ? (
                                                <Check className="w-4 h-4 text-emerald-400" />
                                            ) : isLoss ? (
                                                <X className="w-4 h-4 text-red-400" />
                                            ) : null}
                                        </div>
                                    )}
                                </div>

                                {/* Prices */}
                                <div className="grid grid-cols-2 gap-2 mb-2">
                                    <div>
                                        <div className="text-[10px] text-slate-500 uppercase tracking-tighter">Entry Benchmark</div>
                                        <div className="text-sm font-black text-slate-200">
                                            ₹{(signal.entry_price * 83).toLocaleString()}
                                        </div>
                                    </div>
                                    {signal.exit_price && (
                                        <div>
                                            <div className="text-[10px] text-slate-500 uppercase tracking-tighter">Exit Executable</div>
                                            <div className="text-sm font-black text-slate-200">
                                                ₹{(signal.exit_price * 83).toLocaleString()}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* P&L */}
                                {signal.pnl !== undefined && signal.pnl !== 0 && (
                                    <div className="flex items-center justify-between pt-2 border-t border-slate-700/30">
                                        <span className="text-xs text-slate-500">P&L Attribution</span>
                                        <div className="flex items-center gap-2">
                                            <span className={`text-sm font-bold ${isWin ? 'text-emerald-400' : isLoss ? 'text-red-400' : 'text-slate-400'
                                                }`}>
                                                {signal.pnl >= 0 ? '+' : ''}{signal.pnl.toFixed(2)}R
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* Timestamp */}
                                <div className="mt-2 text-[10px] text-slate-600 font-bold uppercase tracking-widest">
                                    {new Date(signal.created_at).toLocaleString('en-US', {
                                        month: 'short',
                                        day: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit'
                                    })}
                                </div>

                                {/* Status Badge */}
                                {!isClosed && (
                                    <div className="mt-2">
                                        <span className="text-[10px] px-2 py-1 rounded bg-blue-500/20 text-blue-400 font-black tracking-widest">
                                            ACTIVE
                                        </span>
                                    </div>
                                )}
                            </motion.div>
                        );
                    })
                )}
            </div>

            {signals.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                    Showing {signals.length} recent signals
                </div>
            )}
        </div>
    );
};
