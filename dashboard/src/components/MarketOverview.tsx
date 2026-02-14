import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { MarketStat } from '../types';

interface MarketOverviewProps {
    stats: MarketStat[];
}

export const MarketOverview: React.FC<MarketOverviewProps> = ({ stats }) => {
    return (
        <div className="glass-card rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
                <Activity className="w-5 h-5 text-blue-400" />
                <h2 className="text-lg font-bold text-slate-100">Market Overview</h2>
            </div>

            <div className="space-y-3">
                {stats.map((stat, index) => (
                    <motion.div
                        key={stat.symbol}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="group p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 border border-slate-700/30 hover:border-slate-600/50 transition-all cursor-pointer"
                    >
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-bold text-slate-200">{stat.symbol.replace('/USDT', '')}</span>
                            <div className={`flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded ${stat.change >= 0
                                    ? 'bg-emerald-500/10 text-emerald-400'
                                    : 'bg-red-500/10 text-red-400'
                                }`}>
                                {stat.change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {stat.change >= 0 ? '+' : ''}{stat.change.toFixed(2)}%
                            </div>
                        </div>

                        <div className="flex items-baseline justify-between">
                            <span className="text-xl font-bold text-white">
                                ${stat.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                        </div>

                        <div className="flex items-center justify-between mt-2 text-xs text-slate-500">
                            <span>Vol: {stat.volume}</span>
                            <span>24h: ${stat.low24h.toLocaleString()} - ${stat.high24h.toLocaleString()}</span>
                        </div>

                        {/* Mini price bar */}
                        <div className="mt-2 h-1 bg-slate-700/50 rounded-full overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${((stat.price - stat.low24h) / (stat.high24h - stat.low24h)) * 100}%` }}
                                transition={{ duration: 1, delay: index * 0.1 }}
                                className={`h-full ${stat.change >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`}
                            />
                        </div>
                    </motion.div>
                ))}
            </div>

            <div className="mt-4 pt-4 border-t border-slate-700/50">
                <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">Last Update</span>
                    <span className="text-slate-400 font-mono">{new Date().toLocaleTimeString()}</span>
                </div>
            </div>
        </div>
    );
};
