import React from 'react';
import { Activity, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { MarketStat } from '../types';

interface MarketStatsProps {
    stats: MarketStat[];
}

export const MarketStats: React.FC<MarketStatsProps> = ({ stats }) => {
    return (
        <section className="glass-panel rounded-3xl p-6 overflow-hidden relative">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Global Markets</h3>
                <Activity className="w-4 h-4 text-sky-500/50" />
            </div>
            <div className="space-y-5">
                {stats.map((stat) => (
                    <div key={stat.symbol} className="flex items-center justify-between group cursor-pointer">
                        <div>
                            <p className="text-sm font-bold text-white group-hover:text-sky-400 transition-colors">{stat.symbol}</p>
                            <p className="text-[10px] text-slate-500">Vol: {stat.volume}</p>
                        </div>
                        <div className="text-right">
                            <p className="text-sm font-mono font-bold">₹{stat.price.toLocaleString()}</p>
                            <p className={`text-[10px] font-bold flex items-center justify-end gap-1 ${stat.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {stat.change >= 0 ? <ArrowUpRight className="w-2.5 h-2.5" /> : <ArrowDownRight className="w-2.5 h-2.5" />}
                                {Math.abs(stat.change)}%
                            </p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
};
