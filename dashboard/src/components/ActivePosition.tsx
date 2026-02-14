import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, TrendingDown, Target, Shield, Zap, Clock, Layers, Maximize2 } from 'lucide-react';
import { ActiveTrade } from '../types';
import { ConvergenceModal } from './ConvergenceModal';

interface ActivePositionProps {
    activeTrade: ActiveTrade | null;
}

export const ActivePosition: React.FC<ActivePositionProps> = ({ activeTrade }) => {
    const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);

    if (!activeTrade) {
        return (
            <div className="glass-card rounded-xl p-8">
                <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="w-20 h-20 rounded-full bg-slate-800/50 flex items-center justify-center mb-4">
                        <Zap className="w-10 h-10 text-slate-600" />
                    </div>
                    <h3 className="text-xl font-bold text-slate-400 mb-2">No Active Position</h3>
                    <p className="text-sm text-slate-500 max-w-md">
                        System is scanning for high-probability setups. Signal will appear when all criteria are met.
                    </p>
                    <div className="mt-6 flex items-center gap-2 text-xs text-slate-600">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                        <span>Monitoring 3 symbols • 60s interval</span>
                    </div>
                </div>
            </div>
        );
    }

    const isBullish = activeTrade.side === 'LONG';
    const stopDistance = Math.abs(activeTrade.entry_price - activeTrade.stop_loss);
    const stopPercent = (stopDistance / activeTrade.entry_price * 100).toFixed(2);

    return (
        <>
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeTrade.symbol}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="glass-card rounded-xl overflow-hidden"
                >
                    {/* Header */}
                    <div className={`p-6 ${isBullish ? 'bg-gradient-to-r from-emerald-500/10 to-transparent' : 'bg-gradient-to-r from-red-500/10 to-transparent'}`}>
                        <div className="flex items-start justify-between">
                            <div>
                                <div className="flex items-center gap-3 mb-2">
                                    <h2 className="text-2xl font-bold text-white">{activeTrade.symbol}</h2>
                                    <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center gap-2 ${isBullish
                                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                            : 'bg-red-500/20 text-red-400 border border-red-500/30'
                                        }`}>
                                        {isBullish ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                                        {activeTrade.side}
                                    </div>
                                </div>
                                <p className="text-sm text-slate-400">Active Position</p>
                            </div>

                            <div className="text-right">
                                <div className="text-xs text-slate-500 mb-1">Confidence</div>
                                <div className="flex items-center gap-2">
                                    <div className="w-24 h-2 bg-slate-700/50 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${activeTrade.confidence * 100}%` }}
                                            className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                                        />
                                    </div>
                                    <span className="text-sm font-bold text-blue-400">
                                        {(activeTrade.confidence * 100).toFixed(0)}%
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Price Info - Adjusted for INR for display consistency if needed, but keeping USD as per V2 design */}
                    <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="space-y-1">
                            <div className="text-xs text-slate-500 uppercase font-semibold">Entry Price</div>
                            <div className="text-xl font-bold text-white">
                                {activeTrade.entry_price > 0 ? `$${activeTrade.entry_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : 'CALC...'}
                            </div>
                        </div>

                        <div className="space-y-1">
                            <div className="text-xs text-slate-500 uppercase font-semibold flex items-center gap-1">
                                <Shield className="w-3 h-3" />
                                Stop Loss
                            </div>
                            <div className="text-xl font-bold text-red-400">
                                {activeTrade.stop_loss > 0 ? `$${activeTrade.stop_loss.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : 'EST...'}
                            </div>
                            <div className="text-xs text-slate-600">-{stopPercent}%</div>
                        </div>

                        <div className="space-y-1">
                            <div className="text-xs text-slate-500 uppercase font-semibold">Risk:Reward</div>
                            <div className="text-xl font-bold text-purple-400">
                                1:{activeTrade.rr_ratio?.toFixed(1) || '2.5'}
                            </div>
                        </div>

                        <div className="space-y-1">
                            <div className="text-xs text-slate-500 uppercase font-semibold">Duration</div>
                            <div className="text-xl font-bold text-blue-400 flex items-center gap-2">
                                <Clock className="w-4 h-4" />
                                {activeTrade.duration ? `${Math.floor(activeTrade.duration)}m` : '0m'}
                            </div>
                        </div>
                    </div>

                    {/* Take Profit Targets */}
                    <div className="px-6 pb-6 border-b border-white/5">
                        <div className="flex items-center gap-2 mb-3">
                            <Target className="w-4 h-4 text-emerald-400" />
                            <span className="text-sm font-semibold text-slate-300">Take Profit Targets</span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {activeTrade.targets.map((target, index) => (
                                <motion.div
                                    key={index}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.1 }}
                                    className={`p-4 rounded-lg border ${target.hit
                                            ? 'bg-emerald-500/10 border-emerald-500/50'
                                            : 'bg-slate-800/30 border-slate-700/50'
                                        }`}
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-xs font-bold text-slate-400">
                                            {target.label || `TP${index + 1}`}
                                        </span>
                                        {target.hit && (
                                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                        )}
                                    </div>
                                    <div className={`text-lg font-bold ${target.hit ? 'text-emerald-400' : 'text-slate-200'}`}>
                                        {target.price > 0 ? `$${target.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : 'SCAN...'}
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">
                                        {target.price > 0 ? `${((Math.abs(target.price - activeTrade.entry_price) / activeTrade.entry_price) * 100).toFixed(2)}%` : '--'}
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </div>

                    {/* Interactive Actions */}
                    <div className="p-6 bg-slate-900/40 flex gap-4">
                        <button
                            onClick={() => setIsAnalysisOpen(true)}
                            className="flex-1 py-4 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-black rounded-xl transition-all shadow-xl shadow-sky-500/20 flex items-center justify-center gap-3 uppercase tracking-widest text-xs active:scale-[0.98]"
                        >
                            <Layers size={16} /> View Convergence Report
                        </button>
                        <button className="p-4 bg-white/5 hover:bg-white/10 text-white rounded-xl transition-all border border-white/10 group active:scale-95">
                            <Maximize2 size={18} className="group-hover:scale-110 transition-transform" />
                        </button>
                    </div>

                    {/* P&L Display */}
                    {activeTrade.pnl_inr !== undefined && (
                        <div className={`p-4 ${activeTrade.pnl_inr >= 0
                                ? 'bg-emerald-500/10'
                                : 'bg-red-500/10'
                            }`}>
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-semibold text-slate-300">Unrealized P&L</span>
                                <div className="flex items-center gap-2">
                                    <span className={`text-2xl font-bold ${activeTrade.pnl_inr >= 0 ? 'text-emerald-400' : 'text-red-400'
                                        }`}>
                                        {activeTrade.pnl_inr >= 0 ? '+' : ''}
                                        ₹{Math.abs(activeTrade.pnl_inr).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                </motion.div>
            </AnimatePresence>

            <ConvergenceModal
                isOpen={isAnalysisOpen}
                onClose={() => setIsAnalysisOpen(false)}
                symbol={activeTrade.symbol}
                confidence={activeTrade.confidence}
            />
        </>
    );
};
