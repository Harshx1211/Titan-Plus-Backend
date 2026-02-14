import React from 'react';
import { motion } from 'framer-motion';
import { Activity, Zap, TrendingUp } from 'lucide-react';
import { SystemMetrics } from '../types';

interface HeaderProps {
    wsStatus: 'connecting' | 'online' | 'offline';
    metrics: SystemMetrics;
}

export const Header: React.FC<HeaderProps> = ({ wsStatus, metrics }) => {
    const statusColors = {
        online: 'bg-emerald-500',
        offline: 'bg-red-500',
        connecting: 'bg-yellow-500'
    };

    const statusText = {
        online: 'LIVE',
        offline: 'OFFLINE',
        connecting: 'CONNECTING'
    };

    return (
        <motion.header
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card rounded-2xl p-6 mb-6"
        >
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
                {/* Logo & Title */}
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl blur-lg opacity-50" />
                        <div className="relative bg-gradient-to-br from-blue-600 to-purple-600 p-3 rounded-xl">
                            <Activity className="w-7 h-7 text-white" />
                        </div>
                    </div>
                    <div>
                        <h1 className="text-2xl lg:text-3xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                            Titan Brain V3.1
                        </h1>
                        <p className="text-sm text-slate-400 mt-0.5">Institutional Intelligence Core</p>
                    </div>
                </div>

                {/* Live Metrics */}
                <div className="flex items-center gap-4 lg:gap-6">
                    {/* Win Rate */}
                    <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                        <div className="flex flex-col">
                            <span className="text-[10px] text-slate-500 uppercase font-semibold">Win Rate</span>
                            <span className="text-sm font-bold text-emerald-400">
                                {metrics.winRate > 0 ? `${metrics.winRate.toFixed(1)}%` : 'N/A'}
                            </span>
                        </div>
                    </div>

                    {/* Total Signals */}
                    <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <Zap className="w-4 h-4 text-blue-400" />
                        <div className="flex flex-col">
                            <span className="text-[10px] text-slate-500 uppercase font-semibold">Signals</span>
                            <span className="text-sm font-bold text-blue-400">{metrics.totalSignals}</span>
                        </div>
                    </div>

                    {/* Status Indicator */}
                    <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${statusColors[wsStatus]} ${wsStatus === 'online' ? 'animate-pulse' : ''}`} />
                            <span className="text-xs font-semibold text-slate-300">{statusText[wsStatus]}</span>
                        </div>
                    </div>
                </div>
            </div>
        </motion.header>
    );
};
