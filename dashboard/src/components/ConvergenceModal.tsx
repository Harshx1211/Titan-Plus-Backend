import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Shield, Zap, Target, BarChart3, Binary } from 'lucide-react';

interface ConvergenceModalProps {
    isOpen: boolean;
    onClose: () => void;
    symbol: string;
    confidence: number;
}

export const ConvergenceModal: React.FC<ConvergenceModalProps> = ({ isOpen, onClose, symbol, confidence }) => {
    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={onClose}
                    className="absolute inset-0 bg-black/80 backdrop-blur-md"
                />

                <motion.div
                    initial={{ opacity: 0, scale: 0.9, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9, y: 20 }}
                    className="relative w-full max-w-2xl bg-[#0a0c10] border border-white/10 rounded-[2.5rem] overflow-hidden shadow-2xl"
                >
                    {/* Header */}
                    <div className="p-8 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-sky-500/10 to-transparent">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-sky-500/20 flex items-center justify-center text-sky-400">
                                <Binary size={24} />
                            </div>
                            <div>
                                <h2 className="text-xl font-black text-white uppercase tracking-widest">Convergence Report</h2>
                                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.2em]">{symbol} Institutional Analytics</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="p-3 hover:bg-white/5 rounded-full text-slate-400 transition-all">
                            <X size={20} />
                        </button>
                    </div>

                    <div className="p-8 space-y-8">
                        {/* Confluence Metrics */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="p-6 bg-white/5 rounded-3xl border border-white/5">
                                <div className="flex items-center gap-3 text-emerald-400 mb-3">
                                    <Shield size={16} />
                                    <span className="text-[10px] font-black uppercase tracking-widest">SMC Validation</span>
                                </div>
                                <p className="text-sm text-slate-300 font-medium">Market structural break confirmed on 15m/1h timeframes. Liquidity grab detected below range lows.</p>
                            </div>
                            <div className="p-6 bg-white/5 rounded-3xl border border-white/5">
                                <div className="flex items-center gap-3 text-sky-400 mb-3">
                                    <Zap size={16} />
                                    <span className="text-[10px] font-black uppercase tracking-widest">AI Confidence</span>
                                </div>
                                <div className="flex items-center gap-4">
                                    <p className="text-3xl font-black text-white">{(confidence * 100).toFixed(1)}%</p>
                                    <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${confidence * 100}%` }}
                                            className="h-full bg-sky-500"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Checklist */}
                        <div className="space-y-4">
                            <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-widest px-1">Institutional Checklist</h3>
                            <div className="grid grid-cols-1 gap-2">
                                {[
                                    { label: 'Market Structure Alignment (Bullish)', status: true },
                                    { label: 'Order Block Mitigation Search', status: true },
                                    { label: 'Fibonacci OTE Level (0.618 - 0.786)', status: true },
                                    { label: 'Exchange Inflow/Outflow Delta', status: confidence > 0.8 },
                                    { label: 'Volatility Compression Index', status: true }
                                ].map((item, i) => (
                                    <div key={i} className="flex items-center justify-between p-4 bg-white/[0.02] rounded-2xl border border-white/5">
                                        <span className="text-[11px] text-slate-400 font-bold">{item.label}</span>
                                        <div className={`w-2 h-2 rounded-full ${item.status ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-slate-700'}`} />
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Final Advisory */}
                        <div className="p-6 bg-sky-500/5 rounded-3xl border border-sky-500/10 flex items-start gap-4">
                            <Target className="text-sky-400 shrink-0 mt-1" size={20} />
                            <div>
                                <p className="text-[12px] text-white font-bold mb-1 uppercase tracking-tight">Institutional Recommendation</p>
                                <p className="text-[11px] text-sky-400/80 leading-relaxed">Wait for a test of the lower range of the Order Block before final entry. Volatility is expanding; maintain strict risk parity at target levels.</p>
                            </div>
                        </div>
                    </div>

                    <div className="p-8 bg-sky-500/10 border-t border-white/5">
                        <button onClick={onClose} className="w-full py-5 bg-sky-500 hover:bg-sky-400 text-white font-black rounded-2xl transition-all shadow-xl shadow-sky-500/20 uppercase tracking-widest text-xs">
                            Acknowledge Intelligence
                        </button>
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    );
};
