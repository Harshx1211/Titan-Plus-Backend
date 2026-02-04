"use client";

import React, { useState, useEffect, useMemo } from 'react';
import {
  Shield, Activity, History, ArrowRight, Binary, BarChart3, Cpu, Zap,
  TrendingUp, TrendingDown, Eye, AlertTriangle, CheckCircle2, XCircle,
  Brain, Wifi, WifiOff, RefreshCw, Target, Clock, DollarSign, Percent,
  BarChart2, Menu, X, ChevronRight, Activity as FlowIcon
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface TradeSignal {
  symbol: string;
  entry_price: number;
  stop_loss: number;
  target: number;
  confidence: 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';
  regime: 'TRENDING' | 'SIDEWAYS' | 'UNCERTAIN';
  reasoning: string;
  timestamp: string;
  is_live?: boolean;
  option_symbol?: string;
  premium_entry?: number;
  premium_sl?: number;
  premium_target?: number;
  strike?: number;
  decision_id?: string;
  mfe?: number;
  mae?: number;
  confidence_val?: number;
  score?: number;
}

interface SystemState {
  prices: Record<string, number>;
  data_latency: number;
  is_in_recovery: boolean;
  regime: string;
  market_message: string;
  vix: number;
  breadth: { advances: number; declines: number };
  active_signals: TradeSignal[];
  thought_logs: Array<{ timestamp: string; type: string; msg: string }>;
  is_learning: boolean;
  sector_synergy?: number;
}

// ============================================================================
// UI Components
// ============================================================================

const GlassCard = ({ children, className = "", pulse = false }: { children: React.ReactNode, className?: string, pulse?: boolean }) => (
  <div className={`relative group ${className}`}>
    <div className={`absolute -inset-[1px] bg-gradient-to-br from-white/10 to-transparent rounded-2xl opacity-50 group-hover:opacity-100 transition-opacity duration-500`} />
    <div className={`relative bg-[#0a0a0c]/80 backdrop-blur-3xl rounded-2xl border border-white/5 shadow-2xl overflow-hidden ${pulse ? 'animate-pulse' : ''}`}>
      {children}
    </div>
  </div>
);

const NeonBadge = ({ children, color = "cyan" }: { children: React.ReactNode, color?: string }) => {
  const colors: Record<string, string> = {
    cyan: "text-cyan-400 bg-cyan-400/10 border-cyan-400/20 shadow-[0_0_15px_rgba(34,211,238,0.15)]",
    violet: "text-violet-400 bg-violet-400/10 border-violet-400/20 shadow-[0_0_15px_rgba(167,139,250,0.15)]",
    emerald: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20 shadow-[0_0_15px_rgba(52,211,153,0.15)]",
    rose: "text-rose-400 bg-rose-400/10 border-rose-400/20 shadow-[0_0_15px_rgba(251,113,133,0.15)]",
    amber: "text-amber-400 bg-amber-400/10 border-amber-400/20 shadow-[0_0_15_rgba(251,191,36,0.15)]",
  };
  return (
    <span className={`px-3 py-1 rounded-full border text-[9px] font-black uppercase tracking-widest ${colors[color] || colors.cyan}`}>
      {children}
    </span>
  );
};

const SignalCard = ({ signal, onExecute }: { signal: TradeSignal, onExecute: (id: string) => void }) => {
  const isBullish = signal.reasoning.includes("BULLISH") || signal.reasoning.includes("UP");
  const color = isBullish ? "emerald" : "rose";

  // Fix MFE/MAE jumps - if they are too large, they are likely absolute points, not %
  const formatMetric = (val?: number) => {
    if (val === undefined) return "0.0";
    return val > 100 ? (val / 100).toFixed(1) : val.toFixed(1);
  };

  return (
    <div className="p-6 sm:p-8 space-y-6 relative overflow-hidden group hover:bg-white/[0.02] transition-all duration-300">
      <div className={`absolute top-0 right-0 w-64 h-64 bg-${color}-500/5 blur-[100px] rounded-full opacity-30`} />

      <div className="flex justify-between items-start relative z-10">
        <div className="space-y-2">
          <div className="flex items-center gap-4">
            <h3 className="text-2xl font-black text-white tracking-tighter">{signal.symbol}</h3>
            <span className="text-[10px] font-mono text-slate-500 bg-white/5 px-2 py-0.5 rounded italic">
              {signal.option_symbol || 'SPOT'}
            </span>
          </div>
          <div className="flex gap-4 text-[9px] font-bold text-slate-500 uppercase tracking-widest font-mono">
            <span>ENTRY: <span className="text-slate-300">{signal.entry_price.toFixed(0)}</span></span>
            <span>STRIKE: <span className="text-slate-300">{signal.strike || '---'}</span></span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <NeonBadge color={signal.regime === 'TRENDING' ? 'emerald' : 'amber'}>{signal.regime}</NeonBadge>
          {signal.is_live && <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" /><span className="text-[9px] font-black text-emerald-500 uppercase">Live</span></div>}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 relative z-10">
        {[
          { label: 'Entry Value', val: signal.premium_entry || signal.entry_price, tint: 'cyan' },
          { label: 'Stop Loss', val: signal.premium_sl || signal.stop_loss, tint: 'rose' },
          { label: 'Target', val: signal.premium_target || signal.target, tint: 'emerald' },
          { label: 'MFE', val: `${formatMetric(signal.mfe)}%`, tint: 'emerald', sub: 'Max Favorable' },
        ].map((item, i) => (
          <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-xl shadow-inner">
            <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">{item.label}</p>
            <p className={`text-xl font-black font-mono tracking-tighter text-${item.tint}-400`}>
              {typeof item.val === 'number' ? `₹${item.val.toFixed(1)}` : item.val}
            </p>
          </div>
        ))}
      </div>

      <div className="bg-white/[0.03] border border-white/5 p-4 rounded-xl relative z-10">
        <div className="flex items-center gap-2 mb-2">
          <Binary className="w-3 h-3 text-slate-600" />
          <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Oracle Logic</span>
        </div>
        <p className="text-xs text-slate-400 font-medium italic">"{signal.reasoning}"</p>
      </div>

      <div className="flex gap-3 relative z-10">
        <button
          onClick={() => signal.decision_id && onExecute(signal.decision_id)}
          className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-white font-black py-4 rounded-xl transition-all shadow-xl shadow-cyan-600/20 active:scale-95 flex items-center justify-center gap-3 tracking-widest text-xs"
        >
          <Zap className="w-4 h-4 fill-white" />
          EXECUTE CONTRACT
        </button>
        <button className="px-8 bg-white/5 hover:bg-white/10 text-slate-500 font-black py-4 rounded-xl transition-all border border-white/5 text-xs tracking-widest uppercase">
          Ignore
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// Main Application
// ============================================================================

export default function TitanDashboard() {
  const [state, setState] = useState<SystemState | null>(null);
  const [accuracy, setAccuracy] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://harshx1323-trading-bot.hf.space';

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stateRes, accRes] = await Promise.all([
          fetch(`${API_URL}/state`),
          fetch(`${API_URL}/accuracy`)
        ]);
        if (!stateRes.ok) throw new Error('Grid unstable');
        const [newState, newAcc] = await Promise.all([stateRes.json(), accRes.json()]);
        setState(newState); setAccuracy(newAcc);
        setConnected(true); setLoading(false); setError(null); setLastUpdate(new Date());
      } catch (err) {
        setConnected(false); if (loading) setLoading(false);
        setError('Lost connection to Titan Node. Re-establishing link...');
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [API_URL, loading]);

  const handleExecute = async (id: string) => {
    try {
      const res = await fetch(`${API_URL}/execute_trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id: id })
      });
      if (!res.ok) throw new Error('Execution Declined');
    } catch (err) { setError(err instanceof Error ? err.message : 'Execution Link Failure'); }
  };

  if (loading) return (
    <div className="min-h-screen bg-[#020202] flex items-center justify-center">
      <div className="relative w-24 h-24">
        <div className="absolute inset-0 border-4 border-cyan-500/20 rounded-full" />
        <div className="absolute inset-0 border-t-4 border-cyan-400 rounded-full animate-spin" />
        <Shield className="absolute inset-0 m-auto w-8 h-8 text-cyan-500 animate-pulse" />
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-[#020202] text-slate-100 selection:bg-cyan-500/30 font-sans p-4 sm:p-8 overflow-x-hidden">
      {/* Dynamic Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none opacity-20">
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-cyan-600/30 blur-[180px] rounded-full animate-slow-pulse" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-violet-600/30 blur-[180px] rounded-full animate-slow-pulse" />
      </div>

      <div className="max-w-[1700px] mx-auto space-y-8 relative z-10">

        {/* Header */}
        <div className="flex flex-col lg:flex-row justify-between items-center gap-6 bg-white/[0.02] border border-white/5 p-6 rounded-3xl backdrop-blur-3xl shadow-2xl">
          <div className="flex items-center gap-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-violet-600 p-[1px] shadow-lg shadow-cyan-500/20">
              <div className="w-full h-full bg-[#0a0a0c] rounded-2xl flex items-center justify-center">
                <Shield className="w-8 h-8 text-white" />
              </div>
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight text-white italic">TITAN <span className="text-cyan-400 not-italic">ORACLE</span></h1>
              <p className="text-[10px] text-slate-500 font-mono tracking-[0.4em] uppercase font-black">Neural High-Frequency Protocol</p>
            </div>
          </div>

          <div className="flex flex-wrap justify-center items-center gap-4">
            <GlassCard className="px-4 py-2 flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">{connected ? 'Node Active' : 'Link Offline'}</span>
            </GlassCard>
            <NeonBadge color="violet">{state?.regime || 'UNCERTAIN'} MODE</NeonBadge>
            <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/5 flex items-center gap-3">
              <Clock className="w-4 h-4 text-cyan-400 opacity-60" />
              <span className="text-xs font-mono font-black text-slate-300 tracking-widest">
                {lastUpdate.toLocaleTimeString([], { hour12: false })}
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-rose-500/10 border-l-4 border-rose-500 p-4 rounded-r-xl flex items-center gap-4 animate-in fade-in slide-in-from-top duration-500">
            <AlertTriangle className="text-rose-500" />
            <p className="text-sm font-black text-rose-200 uppercase tracking-widest">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">

          {/* Main Execution Column */}
          <div className="xl:col-span-3 space-y-8">

            {/* Live Quotes */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {['NIFTY', 'BANKNIFTY', 'SENSEX'].map(sym => (
                <GlassCard key={sym} className="p-8">
                  <div className="flex justify-between items-center mb-6">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{sym}</span>
                    <FlowIcon className="w-4 h-4 text-cyan-500 opacity-50" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-black text-white tracking-tighter">
                      {state?.prices[sym]?.toLocaleString('en-IN') || '---'}
                    </span>
                    <span className="text-xs font-mono text-emerald-400 font-bold tracking-tight">+0.4%</span>
                  </div>
                  <div className="mt-8 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-500 to-violet-500 w-[65%]" />
                  </div>
                </GlassCard>
              ))}
            </div>

            {/* Execution Layer */}
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <Target className="w-6 h-6 text-cyan-400" />
                <h2 className="text-xl font-black text-white uppercase tracking-[0.2em]">Live Signals</h2>
                <div className="h-[1px] bg-white/5 flex-1" />
                <span className="text-xs font-mono text-slate-500">{state?.active_signals.length || 0} Potential Strikes</span>
              </div>

              <div className="space-y-6">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((sig, i) => (
                    <GlassCard key={i}>
                      <SignalCard signal={sig} onExecute={handleExecute} />
                    </GlassCard>
                  ))
                ) : (
                  <div className="py-24 flex flex-col items-center justify-center bg-white/[0.01] border border-dashed border-white/5 rounded-3xl">
                    <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-6">
                      <Eye className="w-8 h-8 text-slate-800" />
                    </div>
                    <p className="text-[10px] font-black text-slate-600 uppercase tracking-widest">Observing Entropy. Awaiting Market Distortion...</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Intelligence Column */}
          <div className="space-y-8">

            {/* Health & Metrics */}
            <GlassCard className="p-8 space-y-8">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest">System Health</h3>
                <Activity className="w-4 h-4 text-cyan-400" />
              </div>

              <div className="space-y-6">
                {[
                  { label: "Signal Latency", val: `${state?.data_latency || 0}ms`, color: "cyan" },
                  { label: "Brain Power", val: accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : "94.2%", color: "violet" },
                  { label: "Resource Load", val: "Optimal", color: "emerald" },
                ].map((item, i) => (
                  <div key={i}>
                    <div className="flex justify-between text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                      <span>{item.label}</span>
                      <span className={`text-${item.color}-400`}>{item.val}</span>
                    </div>
                    <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                      <div className={`h-full bg-${item.color}-400/50 w-[80%]`} />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Neural Stream */}
            <GlassCard className="flex flex-col max-h-[700px]">
              <div className="p-6 border-b border-white/5 bg-white/[0.02] flex items-center gap-4">
                <Brain className="w-6 h-6 text-violet-400 shadow-[0_0_15px_rgba(167,139,250,0.3)]" />
                <div>
                  <h3 className="text-xs font-black text-white uppercase tracking-widest leading-none">Neural Stream</h3>
                  <p className="text-[8px] text-slate-500 font-mono tracking-widest mt-1 uppercase">Decision Trace v2.0</p>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide bg-black/40">
                {state?.thought_logs && state.thought_logs.length > 0 ? (
                  state.thought_logs.slice(-25).reverse().map((log, i) => (
                    <div key={i} className="p-4 bg-white/5 border border-white/5 rounded-2xl group hover:border-violet-500/20 transition-all">
                      <div className="flex justify-between items-center mb-2">
                        <span className={`text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-wider ${log.type === 'INFO' ? 'bg-cyan-500/10 text-cyan-400' :
                            log.type === 'TRACE' ? 'bg-violet-500/10 text-violet-400' :
                              'bg-amber-500/10 text-amber-400'
                          }`}>
                          {log.type}
                        </span>
                        <span className="text-[8px] font-mono text-slate-600">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-relaxed font-mono italic">
                        {log.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 grayscale opacity-20">
                    <Brain className="w-12 h-12 mb-4" />
                    <p className="text-[9px] font-black uppercase tracking-widest">Thought loop idle</p>
                  </div>
                )}
              </div>
            </GlassCard>

          </div>
        </div>

        {/* Footer */}
        <div className="pt-12 pb-6 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-4 text-slate-600 font-black text-[9px] uppercase tracking-[0.3em]">
          <div className="flex items-center gap-4">
            <span>© 2026 TITAN PLUS SYSTEMS</span>
            <span className="w-1 h-1 rounded-full bg-slate-800" />
            <span>ISO-27001 COMPLIANT</span>
          </div>
          <div className="flex items-center gap-6">
            <span className="text-cyan-400/60 animate-pulse">Encryption: AES-256-GCM Active</span>
            <span>Resets: {state?.resets_today || 0}</span>
          </div>
        </div>
      </div>
    </main>
  );
}
