import React from 'react';
import { Target, Cpu } from 'lucide-react';

export const MetricCards: React.FC = () => {
    return (
        <div className="grid grid-cols-2 gap-6">
            <div className="glass-panel rounded-3xl p-6">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                        <Target size={16} />
                    </div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">Signal Accuracy</h4>
                </div>
                <p className="text-3xl font-black text-white font-outfit">78.4%</p>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4">
                    <div className="bg-emerald-500 h-full rounded-full w-[78%]" />
                </div>
            </div>
            <div className="glass-panel rounded-3xl p-6">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400">
                        <Cpu size={16} />
                    </div>
                    <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">Engine Vitals</h4>
                </div>
                <p className="text-3xl font-black text-white font-outfit">Optimal</p>
                <p className="text-[10px] text-emerald-400 mt-2 font-bold uppercase">Weight Decay Applied</p>
            </div>
        </div>
    );
};
