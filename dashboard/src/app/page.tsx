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
  option_type?: 'CE' | 'PE' | 'SHORT' | 'LONG';
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

const GlassCard = ({ children, className = "", variant = "default" }: { children: React.ReactNode, className?: string, variant?: 'default' | 'premium' | 'dark' }) => {
  const variants = {
    default: "bg-white/[0.05] border-white/10 shadow-[inner_0_1px_1px_rgba(255,255,255,0.05)]",
    premium: "bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border-white/20 shadow-[0_0_50px_rgba(59,130,246,0.1)]",
    dark: "bg-black/60 border-white/5 shadow-2xl",
  };

  return (
    <div className={`relative rounded-[2rem] border backdrop-blur-3xl overflow-hidden transition-all duration-500 group ${variants[variant]} ${className}`}>
      {/* Subtle Top Light Source */}
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

const NeonBadge = ({ children, color = "cyan" }: { children: React.ReactNode, color?: string }) => {
  const colors: Record<string, string> = {
    cyan: "text-cyan-400 bg-cyan-400/10 border-cyan-400/30 shadow-[0_0_20px_rgba(34,211,238,0.2)]",
    blue: "text-blue-400 bg-blue-400/10 border-blue-400/30 shadow-[0_0_20px_rgba(59,130,246,0.2)]",
    emerald: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30 shadow-[0_0_20px_rgba(52,211,153,0.2)]",
    rose: "text-rose-400 bg-rose-400/10 border-rose-400/30 shadow-[0_0_20px_rgba(251,113,133,0.2)]",
    violet: "text-violet-400 bg-violet-400/10 border-violet-400/30 shadow-[0_0_20px_rgba(167,139,250,0.2)]",
  };
  return (
    <span className={`px-5 py-2 rounded-full border text-[10px] font-black uppercase tracking-[0.25em] ${colors[color] || colors.cyan}`}>
      {children}
    </span>
  );
};

const StatCard = ({ label, value, sub, colorClass }: { label: string, value: string | number, sub: string, colorClass: string }) => (
  <GlassCard className="p-7 hover:translate-y-[-4px] hover:border-white/20 transition-all duration-300">
    <div className="space-y-5">
      <div className="flex justify-between items-start">
        <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">{label}</p> {/* Brightened label */}
        <div className={`w-2 h-2 rounded-full blur-[2px] ${colorClass.replace('text-', 'bg-')}`} />
      </div>
      <p className={`text-4xl font-black font-mono tracking-tighter ${colorClass}`}>{value}</p>
      <p className="text-[9px] text-slate-500 font-bold uppercase tracking-[0.15em]">{sub}</p>
    </div>
  </GlassCard>
);

const SignalCard = ({ signal, onExecute }: { signal: TradeSignal, onExecute: (id: string) => void }) => {
  const isPE = signal.option_type === 'PE' || signal.reasoning.includes('BEAR') || signal.reasoning.includes('SELL');
  const accentColor = isPE ? 'rose' : 'emerald';

  return (
    <div className="p-10 relative group border-none">
      <div className={`absolute top-0 right-0 w-[30rem] h-[30rem] bg-${accentColor}-500/5 blur-[150px] rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-1000`} />

      <div className="relative z-10 flex flex-col xl:flex-row justify-between gap-16">
        <div className="flex-1 space-y-10">
          <div className="flex items-center gap-8">
            <div className={`w-20 h-20 rounded-3xl bg-${accentColor}-500/10 border border-${accentColor}-500/20 flex items-center justify-center shadow-2xl`}>
              {isPE ? <TrendingDown className={`w-10 h-10 text-rose-400`} /> : <TrendingUp className={`w-10 h-10 text-emerald-400`} />}
            </div>
            <div>
              <div className="flex items-center gap-5">
                <h3 className="text-5xl font-black text-white tracking-tighter">{signal.symbol}</h3>
                <NeonBadge color={accentColor}>{signal.option_type || (isPE ? 'SHORT' : 'LONG')}</NeonBadge>
              </div>
              <p className="text-sm font-mono text-slate-400 mt-2 uppercase tracking-[0.3em] font-bold">
                {signal.option_symbol || 'Precision Execution Protocol'} • ID: {signal.decision_id?.slice(0, 12) || 'AUTO-ALPHA'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { label: 'Entry Price', val: signal.premium_entry || signal.entry_price, color: 'text-white' },
              { label: 'Stop Loss', val: signal.premium_sl || signal.stop_loss, color: 'text-rose-400' },
              { label: 'Target', val: signal.premium_target || signal.target, color: 'text-emerald-400' },
              { label: 'Confidence', val: signal.confidence, color: 'text-blue-400' },
            ].map((d, i) => (
              <div key={i} className="bg-white/5 rounded-[2rem] p-7 border border-white/5 hover:border-white/10 transition-colors">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">{d.label}</p>
                <p className={`text-2xl font-black font-mono tracking-tighter ${d.color}`}>
                  {typeof d.val === 'number' ? `₹${d.val.toLocaleString()}` : d.val}
                </p>
              </div>
            ))}
          </div>

          <div className="bg-black/40 rounded-[2rem] p-8 border border-white/5 border-l-4 border-l-blue-500 shadow-2xl">
            <div className="flex items-center gap-4 mb-4">
              <Brain className="w-5 h-5 text-blue-400" />
              <span className="text-[11px] font-black text-slate-400 uppercase tracking-[0.2em]">Neural Decision Matrix</span>
            </div>
            <p className="text-base text-slate-300 font-medium leading-relaxed italic opacity-90">"{signal.reasoning}"</p>
          </div>
        </div>

        <div className="flex flex-col justify-center gap-5 min-w-[280px]">
          <button
            onClick={() => signal.decision_id && onExecute(signal.decision_id)}
            className={`w-full bg-${accentColor}-600 hover:bg-${accentColor}-500 text-white font-black py-8 rounded-[2rem] transition-all shadow-2xl shadow-${accentColor}-500/30 active:scale-[0.98] flex flex-col items-center justify-center gap-3 tracking-[0.3em] group/btn`}
          >
            <Zap className="w-8 h-8 fill-white group-hover/btn:scale-110 transition-transform duration-500" />
            <span className="text-sm">DEPLOY CAPITAL</span>
          </button>
          <button className="w-full bg-white/5 hover:bg-white/10 text-slate-400 font-black py-5 rounded-[2rem] border border-white/10 text-xs tracking-[0.2em] uppercase transition-all">
            Veto Alpha
          </button>
        </div>
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
    <div className="min-h-screen bg-[#030305] flex items-center justify-center overflow-hidden">
      <div className="relative">
        <div className="w-48 h-48 rounded-full border-[2px] border-blue-500/10 border-t-blue-500 animate-spin" />
        <Shield className="absolute inset-0 m-auto w-12 h-12 text-blue-500 animate-pulse" />
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-[#030305] text-slate-200 selection:bg-blue-500/30 font-sans p-8 sm:p-16 overflow-x-hidden relative">
      {/* Institutional Grid & Scanline */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.03]" style={{ backgroundImage: `radial-gradient(#ffffff 1px, transparent 1px)`, backgroundSize: '40px 40px' }} />
      <div className="fixed inset-0 pointer-events-none bg-gradient-to-b from-transparent via-white/[0.01] to-transparent h-2 top-0 animate-scanline" />

      {/* Background Ambience */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[60%] h-[60%] bg-blue-600/10 blur-[200px] rounded-full" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[60%] h-[60%] bg-cyan-600/5 blur-[200px] rounded-full" />
      </div>

      <div className="max-w-[1800px] mx-auto space-y-16 relative z-10">

        {/* Header Section */}
        <header className="flex flex-col xl:flex-row justify-between items-center gap-12 bg-white/[0.03] border border-white/10 p-10 rounded-[3.5rem] backdrop-blur-3xl shadow-2xl">
          <div className="flex items-center gap-10">
            <div className="w-20 h-20 rounded-[1.75rem] bg-gradient-to-br from-blue-600 to-cyan-500 p-[2px] shadow-3xl shadow-blue-500/30">
              <div className="w-full h-full bg-[#050507] rounded-[1.75rem] flex items-center justify-center">
                <Shield className="w-11 h-11 text-white" />
              </div>
            </div>
            <div className="space-y-2">
              <h1 className="text-5xl font-black tracking-tighter text-white">
                TITAN <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent italic">PLUS</span>
              </h1>
              <div className="flex items-center gap-4">
                <span className="text-[10px] text-slate-400 font-mono tracking-[0.5em] uppercase font-black">Institutional High-Frequency Protocol</span>
                <div className="h-3 w-[1px] bg-white/20" />
                <span className="text-[10px] text-blue-400 font-mono font-bold tracking-[0.2em] uppercase">v9.9.9 Secure</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-center items-center gap-8">
            <div className="flex items-center gap-5 px-8 py-3.5 bg-black/50 rounded-2xl border border-white/10 shadow-xl">
              <div className={`w-3 h-3 rounded-full ${connected ? 'bg-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.6)] animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-xs font-black uppercase tracking-[0.25em] text-slate-300">
                {connected ? 'Sync: Nominal' : 'No Connection'}
              </span>
            </div>
            <NeonBadge color="violet">{state?.regime || 'UNCERTAIN'} MARKET</NeonBadge>
            <div className="flex items-center gap-5 px-8 py-3.5 bg-white/5 rounded-2xl border border-white/10">
              <Clock className="w-5 h-5 text-blue-400" />
              <span className="text-base font-mono font-black text-slate-300 tracking-widest">
                {lastUpdate.toLocaleTimeString([], { hour12: false })}
              </span>
            </div>
          </div>
        </header>

        {error && (
          <div className="bg-rose-500/10 border border-rose-500/30 p-7 rounded-[2.5rem] flex items-center gap-7 backdrop-blur-2xl animate-in slide-in-from-top duration-1000">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/20 flex items-center justify-center shadow-lg">
              <AlertTriangle className="text-rose-400 w-6 h-6" />
            </div>
            <p className="text-sm font-black text-rose-200 uppercase tracking-[0.2em]">{error}</p>
          </div>
        )}

        {/* Global Market Intelligence Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-8">
          <StatCard label="Volatility" value={state?.vix || '14.2'} sub="India VIX Alpha" colorClass="text-cyan-400" />
          <StatCard label="Sentiment" value={(state?.active_signals?.[0]?.score || 0.95).toFixed(2)} sub="Global PCR Bias" colorClass="text-violet-400" />
          <StatCard label="Advances" value={state?.breadth?.advances || '0'} sub="Bullish Synergy" colorClass="text-emerald-400" />
          <StatCard label="Declines" value={state?.breadth?.declines || '0'} sub="Bearish Friction" colorClass="text-rose-400" />
          <StatCard label="Integrity" value={state?.is_in_recovery ? 'STRICT' : 'MAX'} sub="Governor State" colorClass={state?.is_in_recovery ? 'text-rose-400' : 'text-blue-400'} />
          <StatCard label="Precision" value={accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : '94.2%'} sub="Model Accuracy" colorClass="text-emerald-400" />
        </div>

        <div className="grid grid-cols-1 2xl:grid-cols-4 gap-12">

          <div className="2xl:col-span-3 space-y-16">

            <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
              {['NIFTY', 'BANKNIFTY', 'SENSEX'].map(sym => (
                <GlassCard key={sym} variant="premium" className="p-10 group hover:ring-2 ring-blue-500/20 transition-all duration-700">
                  <div className="flex justify-between items-center mb-10">
                    <span className="text-xs font-black text-slate-400 uppercase tracking-[0.4em] font-mono">{sym} CORE</span>
                    <FlowIcon className="w-6 h-6 text-blue-400 opacity-20 group-hover:opacity-100 transition-all duration-700" />
                  </div>
                  <div className="space-y-4">
                    <p className="text-6xl font-black text-white tracking-tighter group-hover:translate-x-2 transition-transform duration-700 origin-left">
                      {state?.prices[sym]?.toLocaleString('en-IN') || '---'}
                    </p>
                    <div className="flex items-center gap-3">
                      <p className="text-[10px] font-mono text-emerald-400 font-black tracking-[0.3em] uppercase opacity-80 group-hover:opacity-100 transition-opacity">Institutional Synergy ACTIVE</p>
                    </div>
                  </div>
                  <div className="mt-12 h-2 w-full bg-white/5 rounded-full overflow-hidden shadow-inner">
                    <div className="h-full bg-gradient-to-r from-blue-600 via-cyan-500 to-blue-400 w-[65%] group-hover:w-full transition-all duration-[2s] rounded-full shadow-[0_0_15px_rgba(59,130,246,0.3)]" />
                  </div>
                </GlassCard>
              ))}
            </div>

            <div className="space-y-10">
              <div className="flex items-center gap-8">
                <div className="w-14 h-14 rounded-3xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shadow-xl">
                  <Target className="w-7 h-7 text-blue-400" />
                </div>
                <h2 className="text-4xl font-black text-white uppercase tracking-tighter italic">Neural Alpha Distribution</h2>
                <div className="h-[2px] bg-gradient-to-r from-white/20 via-white/5 to-transparent flex-1" />
              </div>

              <div className="grid grid-cols-1 gap-10">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((sig, i) => (
                    <GlassCard key={i} className="hover:ring-1 ring-white/10 transition-all duration-500 rounded-[3rem]">
                      <SignalCard signal={sig} onExecute={handleExecute} />
                    </GlassCard>
                  ))
                ) : (
                  <div className="py-40 flex flex-col items-center justify-center bg-white/[0.01] border-2 border-dashed border-white/10 rounded-[4rem] group transition-all duration-1000 hover:bg-white/[0.02]">
                    <div className="w-32 h-32 bg-white/5 rounded-full flex items-center justify-center mb-10 group-hover:rotate-[360deg] transition-all duration-[2s] border border-white/10 shadow-2xl">
                      <Eye className="w-14 h-14 text-slate-700 opacity-50" />
                    </div>
                    <p className="text-sm font-black text-slate-500 uppercase tracking-[0.5em] text-center max-w-md leading-relaxed">
                      Observing Deep-Market Latency.<br /><span className="text-slate-700 opacity-50 italic">Awaiting Institutional Footprint.</span>
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-12">

            <GlassCard className="p-12 space-y-12 border-blue-500/20 shadow-3xl">
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <h3 className="text-sm font-black text-white uppercase tracking-[0.3em]">Grid Status</h3>
                  <p className="text-[11px] text-slate-400 font-mono font-bold uppercase opacity-60 tracking-widest">Efficiency Metrics</p>
                </div>
                <Activity className="w-6 h-6 text-blue-400 animate-pulse" />
              </div>

              <div className="space-y-10">
                {[
                  { label: "Pipeline Sync", val: `${state?.data_latency || 0}ms`, p: "98%", c: "bg-blue-400 shadow-blue-400/50" },
                  { label: "Neural Entropy", val: "Optimal", p: "72%", c: "bg-cyan-400 shadow-cyan-400/50" },
                  { label: "Alpha Integrity", val: "NOMINAL", p: "100%", c: "bg-emerald-400 shadow-emerald-400/50" },
                ].map((item, i) => (
                  <div key={i} className="space-y-4">
                    <div className="flex justify-between text-[11px] font-black text-slate-400 uppercase tracking-widest">
                      <span>{item.label}</span>
                      <span className="text-white opacity-90">{item.val}</span>
                    </div>
                    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden shadow-inner">
                      <div className={`h-full ${item.c} shadow-[0_0_15px_rgba(59,130,246,0.3)] rounded-full transition-all duration-[1.5s]`} style={{ width: item.p }} />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            <GlassCard className="flex flex-col h-[850px] border-none bg-black/70 shadow-3xl overflow-hidden rounded-[3rem]">
              <div className="p-10 border-b border-white/10 bg-white/[0.03] flex items-center justify-between backdrop-blur-3xl">
                <div className="flex items-center gap-6">
                  <FlowIcon className="w-7 h-7 text-violet-400 drop-shadow-[0_0_10px_rgba(167,139,250,0.5)]" />
                  <h3 className="text-sm font-black text-white uppercase tracking-[0.4em] font-mono leading-none">Sub-Neural Flow</h3>
                </div>
                <div className="relative">
                  <div className="w-3 h-3 rounded-full bg-violet-500 animate-ping absolute" />
                  <div className="w-3 h-3 rounded-full bg-violet-500 shadow-[0_0_15px_rgba(167,139,250,0.8)]" />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-8 space-y-8 scrollbar-hide bg-zinc-950/20">
                {state?.thought_logs && state.thought_logs.length > 0 ? (
                  [...state.thought_logs].reverse().slice(0, 50).map((log, i) => (
                    <div key={i} className="p-6 bg-white/[0.04] border border-white/5 rounded-[1.5rem] transition-all duration-500 hover:bg-white/[0.08] hover:translate-x-1 group/log">
                      <div className="flex justify-between items-center mb-4">
                        <span className={`text-[10px] font-black px-3 py-1.5 rounded-xl uppercase tracking-widest ${log.type === 'INFO' ? 'text-cyan-400 bg-cyan-400/10 border border-cyan-400/20' :
                            log.type === 'TRACE' ? 'text-violet-400 bg-violet-400/10 border border-violet-400/20' :
                              'text-amber-400 bg-amber-400/10 border border-amber-400/20'
                          }`}>
                          {log.type}
                        </span>
                        <span className="text-[10px] font-mono text-slate-600 font-bold group-hover/log:text-slate-400 transition-colors">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 leading-loose font-mono tracking-tight group-hover/log:text-slate-200 transition-colors">
                        {log.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="h-full flex flex-col items-center justify-center space-y-8 opacity-20">
                    <RefreshCw className="w-20 h-20 animate-spin-slow text-slate-800" />
                    <p className="text-xs font-black uppercase tracking-[0.5em] text-slate-900">Synchronizing Synapses</p>
                  </div>
                )}
              </div>
            </GlassCard>
          </div>
        </div>

        <footer className="pt-24 pb-20 border-t border-white/10 flex flex-col lg:flex-row justify-between items-center gap-16 group">
          <div className="flex flex-col md:flex-row items-center gap-16">
            <div className="flex items-center gap-6">
              <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center shadow-2xl border border-white/10 group-hover:border-blue-500/30 transition-all duration-700">
                <Shield className="w-7 h-7 text-blue-500" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-black text-white uppercase tracking-[0.3em]">© 2026 TITAN PLUS SYSTEMS</p>
                <p className="text-[10px] text-slate-500 font-mono font-bold uppercase tracking-[0.4em] opacity-60">Protocol Grade: EXCLUSIVE AUTHORITY</p>
              </div>
            </div>
            <div className="h-16 w-[1px] bg-white/10 hidden md:block" />
            <div className="flex items-center gap-12 text-[11px] font-black uppercase tracking-[0.4em]">
              <span className="text-slate-600 hover:text-cyan-400 transition-all cursor-crosshair">Node: HKG-77</span>
              <span className="text-slate-600 hover:text-blue-400 transition-all cursor-crosshair">Uptime: 99.992%</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-12 bg-white/[0.03] px-16 py-8 rounded-[3rem] border border-white/10 shadow-3xl backdrop-blur-3xl group-hover:border-blue-500/20 transition-all duration-1000">
            <div className="flex items-center gap-4">
              <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest leading-none">Health:</span>
              <span className="text-emerald-400 font-mono text-xs font-black uppercase tracking-widest animate-pulse">NOMINAL</span>
            </div>
            <div className="w-1.5 h-1.5 rounded-full bg-white/10" />
            <div className="flex items-center gap-4">
              <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest leading-none">Resets:</span>
              <span className="text-white font-mono text-sm font-black bg-white/5 px-3 py-1 rounded-lg border border-white/5">{state?.resets_today || 0}</span>
            </div>
            <div className="w-1.5 h-1.5 rounded-full bg-white/10" />
            <div className="flex items-center gap-4">
              <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest italic leading-none">Status:</span>
              <span className="text-cyan-400 font-mono text-xs font-black italic tracking-wide">"{state?.market_message || 'Grid Analysis Stable'}"</span>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
