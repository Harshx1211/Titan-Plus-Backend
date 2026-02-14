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
                    className="relative w-full max-w-2xl bg-[#0a0c10]/90 backdrop-blur-2xl border border-white/10 rounded-[2.5rem] overflow-hidden shadow-[0_0_100px_rgba(56,189,248,0.1)]"
                >
                    {/* Header */}
                    <div className="p-10 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-sky-500/10 via-transparent to-transparent">
                        <div className="flex items-center gap-5">
                            <div className="w-14 h-14 rounded-2xl bg-sky-500/20 flex items-center justify-center text-sky-400 shadow-inner">
                                <Binary size={28} />
                            </div>
                            <div>
                                <h2 className="text-2xl font-black text-white uppercase tracking-tighter">Convergence <span className="text-sky-500 italic">Report</span></h2>
                                <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em]">{symbol} / INST_VALIDATED</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="p-3 hover:bg-white/10 rounded-full text-slate-400 hover:text-white transition-all">
                            <X size={24} />
                        </button>
                    </div>

                    <div className="p-10 space-y-10">
                        {/* Confluence Metrics */}
                        <div className="grid grid-cols-2 gap-6">
                            <div className="p-8 bg-white/5 rounded-3xl border border-white/5 hover:border-sky-500/20 transition-all">
                                <div className="flex items-center gap-3 text-emerald-400 mb-4">
                                    <Shield size={18} />
                                    <span className="text-[11px] font-black uppercase tracking-[0.2em]">SMC Core Validation</span>
                                </div>
                                <p className="text-[13px] text-slate-300 font-bold leading-relaxed">Structural break confirmed across H1/M15. Clear liquidity displacement detected targeting premium zones.</p>
                            </div>
                            <div className="p-8 bg-white/5 rounded-3xl border border-white/5 hover:border-sky-500/20 transition-all">
                                <div className="flex items-center gap-3 text-sky-400 mb-4">
                                    <Zap size={18} />
                                    <span className="text-[11px] font-black uppercase tracking-[0.2em]">Titan AI Confidence</span>
                                </div>
                                <div className="flex flex-col gap-2">
                                    <p className="text-4xl font-black text-white italic">{(confidence * 100).toFixed(1)}%</p>
                                    <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${confidence * 100}%` }}
                                            className="h-full bg-gradient-to-r from-sky-600 to-sky-400 shadow-[0_0_15px_rgba(56,189,248,0.5)]"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Checklist */}
                        <div className="space-y-6">
                            <div className="flex items-center justify-between px-1">
                                <h3 className="text-[11px] text-slate-500 font-black uppercase tracking-[0.3em]">Institutional Verification</h3>
                                <div className="text-[9px] text-sky-500 font-bold px-2 py-0.5 bg-sky-500/10 rounded-md">LIVE SCANNER</div>
                            </div>
                            <div className="grid grid-cols-1 gap-3">
                                {[
                                    { label: 'Market Structure Alignment (Bullish)', status: true },
                                    { label: 'Order Block Mitigation Search', status: true },
                                    { label: 'Fibonacci OTE Level (0.618 - 0.786)', status: true },
                                    { label: 'Exchange Inflow/Outflow Delta', status: confidence > 0.8 },
                                    { label: 'Volatility Compression Index', status: true }
                                ].map((item, i) => (
                                    <div key={i} className="group flex items-center justify-between p-5 bg-white/[0.03] hover:bg-sky-500/[0.03] rounded-2xl border border-white/5 hover:border-sky-500/20 transition-all cursor-default">
                                        <span className="text-xs text-slate-400 group-hover:text-white font-bold transition-colors">{item.label}</span>
                                        <div className={`w-3 h-3 rounded-full ${item.status ? 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.6)]' : 'bg-slate-800'} transition-all`} />
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Final Advisory */}
                        <div className="p-8 bg-sky-500/10 rounded-[2rem] border border-sky-500/20 flex items-start gap-5 shadow-inner">
                            <div className="p-3 bg-sky-500/20 rounded-2xl text-sky-400">
                                <Target size={24} />
                            </div>
                            <div>
                                <p className="text-[13px] text-white font-black mb-2 uppercase tracking-tight">Institutional Target Advisory</p>
                                <p className="text-[12px] text-sky-300 font-bold leading-relaxed">
                                    Titan Brain detects significant institutional accumulation in the current liquidity pool.
                                    Volatility expansion anticipated. Execute with strict risk protocols at the validated entry zones.
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="p-10 bg-black/40 border-t border-white/5">
                        <button
                            onClick={onClose}
                            className="w-full py-6 bg-sky-500 hover:bg-sky-400 active:scale-[0.98] text-white font-black rounded-2xl transition-all shadow-2xl shadow-sky-500/30 uppercase tracking-[0.2em] text-xs flex items-center justify-center gap-3"
                        >
                            Acknowledge Intelligence Core
                        </button>
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    );
};
