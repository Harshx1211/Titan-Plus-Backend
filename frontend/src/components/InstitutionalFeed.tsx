import React from 'react';
import { History } from 'lucide-react';

export const InstitutionalFeed: React.FC = () => {
    return (
        <section className="glass-panel rounded-3xl p-6 h-full font-sans">
            <div className="flex items-center justify-between mb-8">
                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Institutional Feed</h3>
                <History className="w-4 h-4 text-slate-600" />
            </div>

            <div className="space-y-6">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="relative pl-6 pb-6 border-l border-slate-800 last:border-0">
                        <div className="absolute left-[-5px] top-0 w-2.5 h-2.5 rounded-full bg-slate-800 group-hover:bg-sky-500 transition-colors" />
                        <p className="text-[10px] text-slate-500 font-bold mb-1">2h ago</p>
                        <p className="text-xs font-bold text-white mb-1">BTC Signal Completed</p>
                        <p className="text-[10px] text-emerald-400 font-bold uppercase">+1.24R Realized</p>
                    </div>
                ))}
            </div>

            <button className="w-full py-4 mt-4 bg-white/5 hover:bg-white/10 rounded-2xl text-[10px] font-bold uppercase tracking-widest text-slate-400 transition-all">
                Full History Report
            </button>
        </section>
    );
};
