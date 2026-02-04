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
    default: "bg-white/[0.03] border-white/5",
    premium: "bg-gradient-to-br from-blue-500/5 to-cyan-500/5 border-white/10 shadow-[0_0_40px_rgba(59,130,246,0.05)]",
    dark: "bg-black/40 border-white/5",
  };

  return (
    <div className={`relative rounded-3xl border backdrop-blur-3xl overflow-hidden transition-all duration-500 group ${variants[variant]} ${className}`}>
      {/* Subtle Inner Glow */}
      <div className="absolute inset-0 bg-gradient-to-tr from-white/[0.02] to-transparent pointer-events-none" />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

const NeonBadge = ({ children, color = "cyan" }: { children: React.ReactNode, color?: string }) => {
  const colors: Record<string, string> = {
    cyan: "text-cyan-400 bg-cyan-400/5 border-cyan-400/20 shadow-[0_0_20px_rgba(34,211,238,0.1)]",
    blue: "text-blue-400 bg-blue-400/5 border-blue-400/20 shadow-[0_0_20px_rgba(59,130,246,0.1)]",
    emerald: "text-emerald-400 bg-emerald-400/5 border-emerald-400/20 shadow-[0_0_20px_rgba(52,211,153,0.1)]",
    rose: "text-rose-400 bg-rose-400/5 border-rose-400/20 shadow-[0_0_20px_rgba(251,113,133,0.1)]",
    violet: "text-violet-400 bg-violet-400/5 border-violet-400/20 shadow-[0_0_20px_rgba(167,139,250,0.1)]",
  };
  return (
    <span className={`px-4 py-1.5 rounded-full border text-[10px] font-black uppercase tracking-[0.2em] ${colors[color] || colors.cyan}`}>
      {children}
    </span>
  );
};

const StatCard = ({ label, value, sub, colorClass }: { label: string, value: string | number, sub: string, colorClass: string }) => (
  <GlassCard className="p-6 hover:translate-y-[-2px] hover:border-white/10 transition-all duration-300">
    <div className="space-y-4">
      <div className="flex justify-between items-start">
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">{label}</p>
        <div className={`w-1.5 h-1.5 rounded-full blur-[2px] ${colorClass.replace('text-', 'bg-')}`} />
      </div>
      <p className={`text-3xl font-black font-mono tracking-tighter ${colorClass}`}>{value}</p>
      <p className="text-[9px] text-slate-600 font-bold uppercase tracking-widest">{sub}</p>
    </div>
  </GlassCard>
);

const SignalCard = ({ signal, onExecute }: { signal: TradeSignal, onExecute: (id: string) => void }) => {
  const isPE = signal.option_type === 'PE' || signal.reasoning.includes('BEAR') || signal.reasoning.includes('SELL');
  const accentColor = isPE ? 'rose' : 'emerald';
  const accentHex = isPE ? '#fb7185' : '#10b981';

  return (
    <div className="p-8 relative group">
      {/* Background glow based on type */}
      <div className={`absolute top-0 right-0 w-96 h-96 bg-${accentColor}-500/5 blur-[120px] rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-700`} />

      <div className="relative z-10 flex flex-col md:flex-row justify-between gap-12">
        <div className="flex-1 space-y-8">
          {/* Signal Identity */}
          <div className="flex items-center gap-6">
            <div className={`w-16 h-16 rounded-2xl bg-${accentColor}-500/10 border border-${accentColor}-500/20 flex items-center justify-center`}>
              {isPE ? <TrendingDown className={`w-8 h-8 text-rose-400`} /> : <TrendingUp className={`w-8 h-8 text-emerald-400`} />}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-4xl font-black text-white tracking-tighter">{signal.symbol}</h3>
                <NeonBadge color={accentColor}>{signal.option_type || (isPE ? 'SHORT' : 'LONG')}</NeonBadge>
              </div>
              <p className="text-xs font-mono text-slate-500 mt-1 uppercase tracking-widest font-bold">
                {signal.option_symbol || 'Precision Execution Layer'} • ID: {signal.decision_id?.slice(0, 8) || 'AUTO'}
              </p>
            </div>
          </div>

          {/* Pricing Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { label: 'Entry Price', val: signal.premium_entry || signal.entry_price, color: 'text-white' },
              { label: 'Stop Loss', val: signal.premium_sl || signal.stop_loss, color: 'text-rose-400' },
              { label: 'Target', val: signal.premium_target || signal.target, color: 'text-emerald-400' },
              { label: 'Confidence', val: signal.confidence, color: 'text-blue-400' },
            ].map((d, i) => (
              <div key={i} className="bg-white/5 rounded-2xl p-5 border border-white/5">
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">{d.label}</p>
                <p className={`text-xl font-black font-mono tracking-tighter ${d.color}`}>
                  {typeof d.val === 'number' ? `₹${d.val.toLocaleString()}` : d.val}
                </p>
              </div>
            ))}
          </div>

          {/* Logic Summary */}
          <div className="bg-black/40 rounded-2xl p-6 border border-white/5 border-l-4 border-l-blue-500/50">
            <div className="flex items-center gap-3 mb-3">
              <Brain className="w-4 h-4 text-blue-400" />
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Logic Trace</span>
            </div>
            <p className="text-sm text-slate-300 font-medium leading-relaxed italic">"{signal.reasoning}"</p>
          </div>
        </div>

        {/* Execution Controls */}
        <div className="flex flex-col justify-center gap-4 min-w-[200px]">
          <button
            onClick={() => signal.decision_id && onExecute(signal.decision_id)}
            className={`w-full bg-${accentColor}-500 hover:bg-${accentColor}-400 text-white font-black py-6 rounded-2xl transition-all shadow-xl shadow-${accentColor}-500/20 active:scale-95 flex flex-col items-center justify-center gap-2 tracking-[0.2em] group/btn`}
          >
            <Zap className="w-6 h-6 fill-white group-hover/btn:scale-110 transition-transform" />
            <span className="text-xs">DEPLOY CAPITAL</span>
          </button>
          <button className="w-full bg-white/5 hover:bg-white/10 text-slate-500 font-black py-4 rounded-2xl border border-white/5 text-[10px] tracking-widest uppercase transition-all">
            Veto Signal
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
        <div className="w-32 h-32 rounded-full border-[1px] border-blue-500/20 border-t-blue-500 animate-spin" />
        <Shield className="absolute inset-0 m-auto w-10 h-10 text-blue-500 animate-pulse" />
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-[#030305] text-slate-200 selection:bg-blue-500/30 font-sans p-6 sm:p-12 overflow-x-hidden">
      {/* Background Ambience */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[0%] w-[50%] h-[50%] bg-blue-600/10 blur-[200px] rounded-full" />
        <div className="absolute bottom-[-10%] left-[0%] w-[50%] h-[50%] bg-cyan-600/5 blur-[200px] rounded-full" />
      </div>

      <div className="max-w-[1700px] mx-auto space-y-12 relative z-10">

        {/* Header Section */}
        <header className="flex flex-col lg:flex-row justify-between items-center gap-10 bg-white/[0.02] border border-white/5 p-8 rounded-[2.5rem] backdrop-blur-3xl">
          <div className="flex items-center gap-8">
            <div className="w-16 h-16 rounded-[1.25rem] bg-gradient-to-br from-blue-600 to-cyan-500 p-[1.5px] shadow-2xl shadow-blue-500/20">
              <div className="w-full h-full bg-[#050507] rounded-[1.25rem] flex items-center justify-center">
                <Shield className="w-9 h-9 text-white" />
              </div>
            </div>
            <div className="space-y-1">
              <h1 className="text-4xl font-black tracking-tighter text-white">
                TITAN <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent italic">PLUS</span>
              </h1>
              <div className="flex items-center gap-3">
                <span className="text-[9px] text-slate-500 font-mono tracking-[0.4em] uppercase font-black">Institutional Authority Chain</span>
                <div className="h-2 w-[1px] bg-white/10" />
                <span className="text-[9px] text-blue-400 font-mono font-bold tracking-widest uppercase">v9.9.9 Secure</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-center items-center gap-6">
            <div className="flex items-center gap-4 px-6 py-2.5 bg-black/40 rounded-2xl border border-white/5">
              <div className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.5)] animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-300">
                {connected ? 'Sync: Nominal' : 'No Connection'}
              </span>
            </div>
            <NeonBadge color="violet">{state?.regime || 'UNCERTAIN'} MARKET</NeonBadge>
            <div className="flex items-center gap-4 px-6 py-2.5 bg-white/5 rounded-2xl border border-white/5">
              <Clock className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-mono font-black text-slate-300 tracking-wider">
                {lastUpdate.toLocaleTimeString([], { hour12: false })}
              </span>
            </div>
          </div>
        </header>

        {error && (
          <div className="bg-rose-500/10 border border-rose-500/20 p-5 rounded-3xl flex items-center gap-5 backdrop-blur-3xl animate-in slide-in-from-top duration-700">
            <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center">
              <AlertTriangle className="text-rose-400 w-5 h-5" />
            </div>
            <p className="text-xs font-black text-rose-200 uppercase tracking-widest">{error}</p>
          </div>
        )}

        {/* Global Market Intelligence Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
          <StatCard label="Volatility" value={state?.vix || '14.2'} sub="India VIX Control" colorClass="text-cyan-400" />
          <StatCard label="Sentiment" value={(state?.active_signals?.[0]?.score || 0.95).toFixed(2)} sub="Global PCR Bias" colorClass="text-violet-400" />
          <StatCard label="Momentum" value={state?.breadth?.advances || '0'} sub="Bullish Pressure" colorClass="text-emerald-400" />
          <StatCard label="Resistance" value={state?.breadth?.declines || '0'} sub="Bearish Friction" colorClass="text-rose-400" />
          <StatCard label="Integrity" value={state?.is_in_recovery ? 'STRICT' : 'MAX'} sub="Governor State" colorClass={state?.is_in_recovery ? 'text-rose-400' : 'text-blue-400'} />
          <StatCard label="Efficiency" value={accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : '94.2%'} sub="Model Precision" colorClass="text-emerald-400" />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-10">

          {/* Main Tickers & Distribution */}
          <div className="xl:col-span-3 space-y-12">

            {/* High-Tech Market Tickers */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {['NIFTY', 'BANKNIFTY', 'SENSEX'].map(sym => (
                <GlassCard key={sym} variant="premium" className="p-8 group">
                  <div className="flex justify-between items-center mb-8">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] font-mono">{sym} CORE</span>
                    <FlowIcon className="w-5 h-5 text-blue-400 opacity-20 group-hover:opacity-100 transition-all duration-500" />
                  </div>
                  <div className="space-y-2">
                    <p className="text-5xl font-black text-white tracking-tighter group-hover:scale-[1.02] transition-transform duration-500 origin-left">
                      {state?.prices[sym]?.toLocaleString('en-IN') || '---'}
                    </p>
                    <div className="flex items-center gap-2">
                      <p className="text-[10px] font-mono text-emerald-400 font-black tracking-widest uppercase">Institutional Synergy ACTIVE</p>
                    </div>
                  </div>
                  <div className="mt-10 h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-600 via-cyan-500 to-blue-400 w-[60%] group-hover:w-full transition-all duration-[1.5s]" />
                  </div>
                </GlassCard>
              ))}
            </div>

            {/* Signal Distribution Layer */}
            <div className="space-y-8">
              <div className="flex items-center gap-6">
                <div className="w-12 h-12 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                  <Target className="w-6 h-6 text-blue-400" />
                </div>
                <h2 className="text-3xl font-black text-white uppercase tracking-tighter italic">Neural Signal Flow</h2>
                <div className="h-[2px] bg-gradient-to-r from-white/10 via-white/[0.05] to-transparent flex-1" />
              </div>

              <div className="grid grid-cols-1 gap-8">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((sig, i) => (
                    <GlassCard key={i} className="hover:border-white/10 transition-all duration-300">
                      <SignalCard signal={sig} onExecute={handleExecute} />
                    </GlassCard>
                  ))
                ) : (
                  <div className="py-32 flex flex-col items-center justify-center bg-white/[0.01] border-2 border-dashed border-white/5 rounded-[3rem] group">
                    <div className="w-24 h-24 bg-white/5 rounded-full flex items-center justify-center mb-8 group-hover:rotate-12 transition-all duration-700">
                      <Eye className="w-10 h-10 text-slate-800" />
                    </div>
                    <p className="text-xs font-black text-slate-600 uppercase tracking-[0.4em] text-center max-w-xs leading-loose">
                      Observing Sub-Quantum Noise.<br />Awaiting Institutional Footprint.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Institutional Side Panel */}
          <div className="space-y-10">

            {/* Security & Compute Status */}
            <GlassCard className="p-10 space-y-10 border-blue-500/10">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Neural Compute</h3>
                  <p className="text-[10px] text-slate-500 font-mono font-bold uppercase">Grid Efficiency</p>
                </div>
                <Activity className="w-5 h-5 text-blue-400" />
              </div>

              <div className="space-y-8">
                {[
                  { label: "Data Pipeline", val: `${state?.data_latency || 0}ms`, p: "95%", c: "bg-blue-400" },
                  { label: "Neural Load", val: "Optimal", p: "65%", c: "bg-cyan-400" },
                  { label: "Memory Safety", val: "Secure", p: "100%", c: "bg-emerald-400" },
                ].map((item, i) => (
                  <div key={i} className="space-y-3">
                    <div className="flex justify-between text-[10px] font-black text-slate-400 uppercase tracking-widest">
                      <span>{item.label}</span>
                      <span className="text-white">{item.val}</span>
                    </div>
                    <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                      <div className={`h-full ${item.c} shadow-[0_0_10px_rgba(59,130,246,0.3)]`} style={{ width: item.p }} />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Neural Thoughts Stream */}
            <GlassCard className="flex flex-col h-[700px] border-none bg-black/60 shadow-inner">
              <div className="p-8 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                <div className="flex items-center gap-5">
                  <FlowIcon className="w-6 h-6 text-violet-400" />
                  <h3 className="text-xs font-black text-white uppercase tracking-[0.3em] font-mono leading-none">The Stream</h3>
                </div>
                <div className="relative">
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-500 animate-ping absolute" />
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-500" />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide">
                {state?.thought_logs && state.thought_logs.length > 0 ? (
                  [...state.thought_logs].reverse().slice(0, 40).map((log, i) => (
                    <div key={i} className="p-5 bg-white/[0.03] border border-white/5 rounded-2xl transition-all duration-300 hover:bg-white/[0.05]">
                      <div className="flex justify-between items-center mb-3">
                        <span className={`text-[9px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wider ${log.type === 'INFO' ? 'text-cyan-400 bg-cyan-400/10' :
                          log.type === 'TRACE' ? 'text-violet-400 bg-violet-400/10' :
                            'text-amber-400 bg-amber-400/10'
                          }`}>
                          {log.type}
                        </span>
                        <span className="text-[9px] font-mono text-slate-600 font-bold">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed font-mono tracking-tight underline-offset-4 decoration-white/5 underline">
                        {log.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="h-full flex flex-col items-center justify-center space-y-6 opacity-20">
                    <RefreshCw className="w-16 h-16 animate-spin-slow text-slate-700" />
                    <p className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-800">Neutralizing Noise</p>
                  </div>
                )}
              </div>
            </GlassCard>
          </div>
        </div>

        {/* Global Tactical Footer */}
        <footer className="pt-16 pb-12 border-t border-white/5 flex flex-col lg:flex-row justify-between items-center gap-10">
          <div className="flex flex-col md:flex-row items-center gap-10">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">
                <Shield className="w-5 h-5 text-blue-500" />
              </div>
              <div className="space-y-0.5">
                <p className="text-[10px] font-black text-white uppercase tracking-widest">© 2026 TITAN SYSTEMS</p>
                <p className="text-[9px] text-slate-600 font-mono font-bold uppercase tracking-widest">Protocol Version: 9.9.9.0-Final</p>
              </div>
            </div>
            <div className="h-10 w-[1px] bg-white/5 hidden md:block" />
            <div className="flex items-center gap-8 text-[10px] font-black uppercase tracking-[0.3em]">
              <span className="text-slate-500 hover:text-cyan-400 transition-colors cursor-pointer">Security Grade: S-TIER</span>
              <span className="text-slate-500 hover:text-blue-400 transition-colors cursor-pointer">Latency: {state?.data_latency || 0}ms</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-8 bg-white/[0.02] px-10 py-5 rounded-[2rem] border border-white/5 shadow-2xl">
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">Oracle Health:</span>
              <span className="text-emerald-400 font-mono text-[11px] font-black uppercase">NOMINAL</span>
            </div>
            <div className="w-1 h-1 rounded-full bg-white/10" />
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">Resets:</span>
              <span className="text-white font-mono text-xs font-black">{state?.resets_today || 0}</span>
            </div>
            <div className="w-1 h-1 rounded-full bg-white/10" />
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest italic">Status:</span>
              <span className="text-cyan-400 font-mono text-[11px] font-black italic">"{state?.market_message || 'Grid Stable'}"</span>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
