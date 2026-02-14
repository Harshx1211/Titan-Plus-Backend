import React from 'react';
import { motion } from 'framer-motion';
import { Server, Cpu, Database, Wifi } from 'lucide-react';

interface SystemStatusProps {
    wsStatus: 'connecting' | 'online' | 'offline';
    aiVersion: string;
    uptime: string;
    endpoint?: string;
}

export const SystemStatus: React.FC<SystemStatusProps> = ({ wsStatus, aiVersion, uptime, endpoint }) => {
    const statusConfig = {
        online: { color: 'emerald', text: 'Online', icon: Wifi },
        offline: { color: 'red', text: 'Offline', icon: Wifi },
        connecting: { color: 'yellow', text: 'Connecting', icon: Wifi }
    };

    const config = statusConfig[wsStatus];

    return (
        <div className="glass-card rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
                <Server className="w-5 h-5 text-cyan-400" />
                <h2 className="text-lg font-bold text-slate-100">System Status</h2>
            </div>

            <div className="space-y-4">
                {/* Connection Status */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg bg-${config.color}-500/10`}>
                            <config.icon className={`w-4 h-4 text-${config.color}-400`} />
                        </div>
                        <div>
                            <div className="text-[10px] text-slate-500 mb-0.5 uppercase font-bold tracking-widest">Connection</div>
                            <div className={`text-sm font-bold text-${config.color}-400`}>
                                {config.text}
                            </div>
                        </div>
                    </div>
                    <div className={`w-2 h-2 rounded-full bg-${config.color}-500 ${wsStatus === 'online' ? 'animate-pulse' : ''}`} />
                </div>

                {/* AI Version */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/10">
                            <Cpu className="w-4 h-4 text-purple-400" />
                        </div>
                        <div>
                            <div className="text-[10px] text-slate-500 mb-0.5 uppercase font-bold tracking-widest">AI Model</div>
                            <div className="text-sm font-black text-purple-400 font-mono">
                                {aiVersion}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Database */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/10">
                            <Database className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div>
                            <div className="text-[10px] text-slate-500 mb-0.5 uppercase font-bold tracking-widest">Database</div>
                            <div className="text-sm font-bold text-emerald-400">
                                Supabase Active
                            </div>
                        </div>
                    </div>
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>

                {/* Uptime */}
                <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
                    <div className="flex items-center justify-between">
                        <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Uptime</span>
                        <span className="text-sm font-black text-blue-400 font-mono">{uptime}</span>
                    </div>
                </div>
            </div>

            {/* System Info */}
            <div className="mt-4 pt-4 border-t border-slate-700/50 space-y-2 text-[10px]">
                <div className="flex items-center justify-between text-slate-500 font-bold uppercase tracking-widest">
                    <span>Neural Link</span>
                    <span className="text-blue-400 truncate max-w-[150px]">{endpoint?.replace('https://', '')}</span>
                </div>
            </div>
        </div>
    );
};
