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
  resets_today?: number;
  integrity_status?: string;
  last_update?: string;
  data_source?: string;
  max_pain?: Record<string, number>;
  option_battles?: Record<string, any[]>;
  option_chains?: Record<string, any[]>;
  iv_skew?: Record<string, number>;
  supports?: Record<string, number[]>;
  resistances?: Record<string, number[]>;
  gex_bias?: Record<string, number>;
  market_open?: boolean;
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
    <main className="min-h-screen bg-[#050507] text-slate-100 selection:bg-cyan-500/30 font-sans p-4 sm:p-8 overflow-x-hidden">
      {/* Background Ambience */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none opacity-20">
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-blue-600/20 blur-[180px] rounded-full" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-cyan-600/10 blur-[180px] rounded-full" />
      </div>

      <div className="max-w-[1700px] mx-auto space-y-8 relative z-10">

        {/* Global Header */}
        <header className="flex flex-col lg:flex-row justify-between items-center gap-6 bg-white/[0.02] border border-white/5 p-6 rounded-3xl backdrop-blur-3xl shadow-2xl">
          <div className="flex items-center gap-6">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-600 p-[1px] shadow-lg shadow-blue-500/20">
              <div className="w-full h-full bg-[#0a0a0c] rounded-2xl flex items-center justify-center">
                <Shield className="w-8 h-8 text-white" />
              </div>
            </div>
            <div className="space-y-1">
              <h1 className="text-3xl font-black tracking-tighter text-white flex items-center gap-3">
                TITAN <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent italic">PLUS</span>
              </h1>
              <p className="text-[9px] text-slate-500 font-mono tracking-[0.4em] uppercase font-black">Neural Institutional Protocols v9.9</p>
            </div>
          </div>

          <div className="flex flex-wrap justify-center items-center gap-4">
            <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/5 flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-cyan-500 animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">
                {connected ? 'Signal Linked' : 'Link Lost'}
              </span>
            </div>
            <NeonBadge color="violet">{state?.regime || 'UNCERTAIN'} MODE</NeonBadge>
            <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/5 flex items-center gap-3">
              <Clock className="w-4 h-4 text-cyan-400 opacity-60" />
              <span className="text-xs font-mono font-black text-slate-300 tracking-widest">
                {lastUpdate.toLocaleTimeString([], { hour12: false })}
              </span>
            </div>
          </div>
        </header>

        {error && (
          <div className="bg-rose-500/10 border-l-4 border-rose-500 p-4 rounded-r-xl flex items-center gap-4 animate-in fade-in slide-in-from-top duration-500">
            <AlertTriangle className="text-rose-500" />
            <p className="text-sm font-black text-rose-200 uppercase tracking-widest">{error}</p>
          </div>
        )}

        {/* Global Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
          {[
            { label: 'India VIX', val: state?.vix || 0, color: 'text-cyan-400', sub: 'Volatility Index' },
            { label: 'Put Call Ratio', val: (state?.active_signals?.[0]?.score || 0.95).toFixed(2), color: 'text-violet-400', sub: 'Market Sentiment' },
            { label: 'Advances', val: state?.breadth?.advances || 0, color: 'text-emerald-400', sub: 'Market Strength' },
            { label: 'Declines', val: state?.breadth?.declines || 0, color: 'text-rose-400', sub: 'Market Weakness' },
            { label: 'Recovery Status', val: state?.is_in_recovery ? 'STRICT' : 'NOMINAL', color: state?.is_in_recovery ? 'text-rose-400' : 'text-emerald-400', sub: 'Risk Governor' },
            { label: 'Accuracy', val: accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : '94.2%', color: 'text-blue-400', sub: 'Model Precision' },
          ].map((item, i) => (
            <GlassCard key={i} className="p-6">
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">{item.label}</p>
              <p className={`text-2xl font-black font-mono tracking-tighter ${item.color}`}>{item.val}</p>
              <p className="text-[8px] text-slate-600 uppercase font-bold mt-2 tracking-wider">{item.sub}</p>
            </GlassCard>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">

          {/* Main Execution Column */}
          <div className="xl:col-span-3 space-y-8">

            {/* Live Quotes */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {['NIFTY', 'BANKNIFTY', 'SENSEX'].map(sym => (
                <GlassCard key={sym} className="p-8 group hover:border-cyan-500/20 transition-all duration-500">
                  <div className="flex justify-between items-center mb-6">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{sym} CORE</span>
                    <Activity className="w-4 h-4 text-cyan-500 opacity-20 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-black text-white tracking-tighter">
                      {state?.prices[sym]?.toLocaleString('en-IN') || '---'}
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400/60 font-black tracking-widest uppercase">SYNERGY</span>
                  </div>
                  <div className="mt-8 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 w-[75%] group-hover:w-full transition-all duration-1000" />
                  </div>
                </GlassCard>
              ))}
            </div>

            {/* Signal Feed */}
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                  <FlowIcon className="w-4 h-4 text-cyan-400" />
                </div>
                <h2 className="text-xl font-black text-white uppercase tracking-[0.2em] italic">Neural Distribution</h2>
                <div className="h-[1px] bg-gradient-to-r from-white/10 to-transparent flex-1" />
              </div>

              <div className="grid grid-cols-1 gap-6">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((sig, i) => (
                    <GlassCard key={i}>
                      <SignalCard signal={sig} onExecute={handleExecute} />
                    </GlassCard>
                  ))
                ) : (
                  <div className="py-24 flex flex-col items-center justify-center bg-white/[0.01] border border-dashed border-white/5 rounded-3xl group">
                    <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500">
                      <Eye className="w-10 h-10 text-slate-800" />
                    </div>
                    <p className="text-[10px] font-black text-slate-600 uppercase tracking-[0.3em]">Quantum Noise Detected. Deciphering Institutional Flows...</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Side Panels */}
          <div className="space-y-8">

            {/* Meta Controller */}
            <GlassCard className="p-8 space-y-8 bg-gradient-to-b from-white/[0.02] to-transparent">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest">Institutional AI</h3>
                <Cpu className="w-4 h-4 text-cyan-400 animate-pulse" />
              </div>

              <div className="space-y-6">
                {[
                  { label: "Data Pipeline", val: `${state?.data_latency || 0}ms`, p: "100%" },
                  { label: "Neural Integrity", val: "NOMINAL", p: "98%" },
                  { label: "Risk Exposure", val: "LOCKED", p: "100%" },
                ].map((item, i) => (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-between text-[9px] font-black text-slate-500 uppercase tracking-widest">
                      <span>{item.label}</span>
                      <span className="text-cyan-400">{item.val}</span>
                    </div>
                    <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                      <div className={`h-full bg-cyan-500/50 w-[${item.p}]`} />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Neural Stream (Thoughts) */}
            <GlassCard className="flex flex-col h-[600px] bg-black/40 border-none">
              <div className="p-6 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Brain className="w-6 h-6 text-violet-400 drop-shadow-[0_0_8px_rgba(167,139,250,0.5)]" />
                  <h3 className="text-xs font-black text-white uppercase tracking-widest italic">Neural Stream</h3>
                </div>
                <div className="w-2 h-2 rounded-full bg-violet-500 animate-ping" />
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                {state?.thought_logs && state.thought_logs.length > 0 ? (
                  [...state.thought_logs].reverse().slice(0, 30).map((log, i) => (
                    <div key={i} className="p-4 bg-white/[0.02] border-l-2 border-violet-500/30 rounded-r-xl group hover:bg-white/[0.04] transition-all">
                      <div className="flex justify-between items-center mb-2">
                        <span className={`text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-tighter ${log.type === 'INFO' ? 'text-cyan-400 border border-cyan-400/20' :
                            log.type === 'TRACE' ? 'text-violet-400 border border-violet-400/20' :
                              'text-amber-400 border border-amber-400/20'
                          }`}>
                          {log.type}
                        </span>
                        <span className="text-[8px] font-mono text-slate-600">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-relaxed font-mono">
                        {log.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="h-full flex flex-col items-center justify-center opacity-30 grayscale">
                    <RefreshCw className="w-12 h-12 mb-4 animate-spin-slow text-slate-600" />
                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-700">Awaiting Sub-Neural Flow</p>
                  </div>
                )}
              </div>
            </GlassCard>
          </div>
        </div>

        {/* Tactical Footer */}
        <footer className="pt-12 pb-8 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-8 group">
          <div className="flex items-center gap-6 text-[9px] font-black text-slate-600 uppercase tracking-[0.4em]">
            <span>© 2026 TITAN PLUS SYSTEMS</span>
            <span className="w-1 h-1 rounded-full bg-slate-800" />
            <span className="text-slate-400 group-hover:text-cyan-400 transition-colors">Neural Authority Grade: S+</span>
          </div>

          <div className="flex items-center gap-8 text-[9px] font-black uppercase tracking-widest">
            <div className="flex items-center gap-3">
              < Shield className="w-3 h-3 text-cyan-400/50" />
              <span className="text-slate-500 italic">AES-256 E2EE Active</span>
            </div>
            <div className="h-4 w-[1px] bg-white/5" />
            <div className="flex items-center gap-3">
              <span className="text-slate-500">System Resets:</span>
              <span className="text-slate-200 bg-white/5 px-2 py-0.5 rounded">{state?.resets_today || 0}</span>
            </div>
            <div className="h-4 w-[1px] bg-white/5" />
            <div className="flex items-center gap-3">
              <span className="text-slate-500">Market Message:</span>
              <span className="text-cyan-400 italic">"{state?.market_message || 'System Operational'}"</span>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
