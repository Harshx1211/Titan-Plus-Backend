import React from 'react';
import { motion } from 'framer-motion';
import { Brain, Globe } from 'lucide-react';

interface HeaderProps {
    wsStatus: 'connecting' | 'online' | 'offline';
}

export const Header: React.FC<HeaderProps> = ({ wsStatus }) => {
    return (
        <header className="flex flex-col md:flex-row justify-between items-center mb-10 gap-6">
            <div className="flex items-center gap-5">
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
                    className="w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center shadow-[0_0_30px_rgba(56,189,248,0.3)]"
                >
                    <Brain className="text-white w-8 h-8" />
                </motion.div>
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white font-outfit uppercase">
                        Titan<span className="text-sky-400">Brain</span> <span className="text-sm font-light opacity-50 ml-2">V3.1.0</span>
                    </h1>
                    <div className="flex items-center gap-3 mt-1">
                        <span className="text-[10px] text-sky-400 font-bold uppercase tracking-[0.2em]">Institutional Intelligence Core</span>
                        <div className="h-1 w-1 rounded-full bg-slate-700" />
                        <div className="flex items-center gap-1.5">
                            <Globe className="w-3 h-3 text-slate-500" />
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">USD/INR Live</span>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-4">
                <div className="flex flex-col items-end">
                    <div className="flex items-center gap-2 px-4 py-2 bg-white/5 rounded-full border border-white/10 glass-panel">
                        <div className={`w-2 h-2 rounded-full ${wsStatus === 'online' ? 'bg-emerald-500 shadow-[0_0_10px_#10b981]' : 'bg-rose-500 shadow-[0_0_10px_#ef4444]'} animate-pulse`} />
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{wsStatus}</span>
                    </div>
                </div>
            </div>
        </header>
    );
};
