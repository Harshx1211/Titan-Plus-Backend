import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, Target, Award, Zap } from 'lucide-react';
import { SystemMetrics } from '../types';

interface PerformanceMetricsProps {
    metrics: SystemMetrics;
}

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ metrics }) => {
    const cards = [
        {
            title: 'Win Rate',
            value: metrics.winRate > 0 ? `${metrics.winRate.toFixed(1)}%` : 'N/A',
            subtitle: metrics.recentWinRate ? `Recent: ${metrics.recentWinRate.toFixed(1)}%` : 'No recent data',
            icon: Award,
            color: 'emerald',
            gradient: 'from-emerald-500 to-green-600'
        },
        {
            title: 'Avg R-Multiple',
            value: metrics.avgRMultiple > 0 ? `${metrics.avgRMultiple.toFixed(2)}R` : 'N/A',
            subtitle: 'Risk-Reward Ratio',
            icon: Target,
            color: 'blue',
            gradient: 'from-blue-500 to-cyan-600'
        },
        {
            title: 'Profit Factor',
            value: metrics.profitFactor > 0 ? metrics.profitFactor.toFixed(2) : 'N/A',
            subtitle: 'Gross Profit / Gross Loss',
            icon: TrendingUp,
            color: 'purple',
            gradient: 'from-purple-500 to-pink-600'
        },
        {
            title: 'Total Signals',
            value: metrics.totalSignals.toString(),
            subtitle: `AI Confidence: ${metrics.aiConfidence}%`,
            icon: Zap,
            color: 'yellow',
            gradient: 'from-yellow-500 to-orange-600'
        }
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {cards.map((card, index) => {
                const Icon = card.icon;
                return (
                    <motion.div
                        key={card.title}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="glass-card rounded-xl p-5 hover:scale-105 transition-transform cursor-pointer group"
                    >
                        <div className="flex items-start justify-between mb-3">
                            <div className={`p-2 rounded-lg bg-gradient-to-br ${card.gradient} bg-opacity-10`}>
                                <Icon className="w-5 h-5 text-white" />
                            </div>
                            <div className={`w-2 h-2 rounded-full bg-${card.color}-500 animate-pulse`} />
                        </div>

                        <div className="space-y-1">
                            <h3 className="text-xs text-slate-500 font-semibold uppercase tracking-wide">
                                {card.title}
                            </h3>
                            <p className="text-2xl font-bold text-white group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-white group-hover:to-slate-400 transition-all">
                                {card.value}
                            </p>
                            <p className="text-xs text-slate-600">{card.subtitle}</p>
                        </div>
                    </motion.div>
                );
            })}
        </div>
    );
};
