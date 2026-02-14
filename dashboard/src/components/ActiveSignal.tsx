import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Layers, Maximize2 } from 'lucide-react';
import { ActiveTrade } from '../types';
import { ConvergenceModal } from './ConvergenceModal';

interface ActiveSignalProps {
    activeTrade: ActiveTrade | null;
}

export const ActiveSignal: React.FC<ActiveSignalProps> = ({ activeTrade }) => {
    const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);

    if (!activeTrade) {
        return (
            <div className="glass-panel rounded-[2rem] p-20 flex flex-col items-center justify-center text-center border-dashed border-2 border-slate-800 h-full">
                <motion.div
                    animate={{ y: [0, -10, 0] }}
                    transition={{ duration: 4, repeat: Infinity }}
                    className="w-24 h-24 bg-slate-900 rounded-full flex items-center justify-center mb-6"
                >
                    <TrendingUp className="w-12 h-12 text-slate-700" />
                </motion.div>
                <h3 className="text-xl font-bold text-slate-400 uppercase tracking-widest font-outfit">Awaiting High-Prob Signal</h3>
                <p className="text-sm text-slate-600 mt-2 max-w-xs">Brain V3.1 is currently scanning global liquidity pools for institutional setups.</p>
            </div>
        );
    }

    return (
        <>
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`glass-panel rounded-[2rem] p-8 border-t-8 ${activeTrade.side === 'LONG' ? 'border-t-emerald-500 shadow-[0_0_50px_rgba(16,185,129,0.1)]' : 'border-t-rose-500 shadow-[0_0_50px_rgba(239,68,68,0.1)]'} relative overflow-hidden`}
            >
                <div className="absolute top-0 right-0 p-8 opacity-5">
                    {activeTrade.side === 'LONG' ? <TrendingUp size={200} /> : <TrendingDown size={200} />}
                </div>

                <div className="relative z-10">
                    <div className="flex justify-between items-start mb-10">
                        <div className="flex gap-6">
                            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${activeTrade.side === 'LONG' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                                {activeTrade.side === 'LONG' ? <TrendingUp size={32} /> : <TrendingDown size={32} />}
                            </div>
                            <div>
                                <div className="flex items-center gap-3">
                                    <h2 className="text-4xl font-bold text-white font-outfit uppercase tracking-tight">{activeTrade.symbol}</h2>
                                    <span className={`px-3 py-1 rounded-full text-xs font-black tracking-widest ${activeTrade.side === 'LONG' ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white shadow-[0_0_20px_rgba(239,68,68,0.3)]'}`}>
                                        {activeTrade.side} ADVISORY
                                    </span>
                                </div>
                                <p className="text-slate-400 mt-1 uppercase text-xs tracking-[0.3em] font-medium">Institutional Setup Validated</p>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-xs text-slate-500 uppercase font-black mb-1 tracking-widest">AI Confidence</p>
                            <p className="text-3xl font-black text-sky-400 font-outfit">{(activeTrade.confidence * 100).toFixed(1)}%</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-6 mb-10">
                        <div className="bg-white/5 rounded-2xl p-5 border border-white/5">
                            <p className="text-[10px] text-slate-500 uppercase font-bold mb-2">Entry Recommended</p>
                            <p className="text-2xl font-mono font-bold text-white">₹{(Number(activeTrade.entry_price || 0) * 83).toLocaleString()}</p>
                        </div>
                        <div className="bg-white/5 rounded-2xl p-5 border border-white/5">
                            <p className="text-[10px] text-slate-500 uppercase font-bold mb-2">Primary Target</p>
                            <p className="text-2xl font-mono font-bold text-emerald-400">₹{(Number(activeTrade.targets[0]?.price || 0) * 83).toLocaleString()}</p>
                        </div>
                        <div className="bg-white/5 rounded-2xl p-5 border border-white/5">
                            <p className="text-[10px] text-slate-500 uppercase font-bold mb-2">Stop Loss (Cap)</p>
                            <p className="text-2xl font-mono font-bold text-rose-400">₹{(Number(activeTrade.stop_loss || 0) * 83).toLocaleString()}</p>
                        </div>
                    </div>

                    <div className="flex gap-4">
                        <button
                            onClick={() => setIsAnalysisOpen(true)}
                            className="flex-1 py-5 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-black rounded-2xl transition-all shadow-xl shadow-sky-500/20 flex items-center justify-center gap-3 uppercase tracking-widest text-sm"
                        >
                            <Layers size={18} /> View Convergence Analysis
                        </button>
                        <button
                            onClick={() => setIsAnalysisOpen(true)}
                            className="p-5 bg-white/5 hover:bg-white/10 text-white rounded-2xl transition-all border border-white/10 group active:scale-95"
                        >
                            <Maximize2 size={20} className="group-hover:scale-110 transition-transform" />
                        </button>
                    </div>
                </div>
            </motion.div>

            <ConvergenceModal
                isOpen={isAnalysisOpen}
                onClose={() => setIsAnalysisOpen(false)}
                symbol={activeTrade.symbol}
                confidence={activeTrade.confidence}
            />
        </>
    );
};
    );
};
