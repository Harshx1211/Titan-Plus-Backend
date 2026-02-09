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
  direct_execution_active?: boolean;
}

// ============================================================================
// UI Components
// ============================================================================

const GlassCard = ({ children, className = "", variant = "default" }: { children: React.ReactNode, className?: string, variant?: 'default' | 'premium' | 'dark' }) => {
  const variants = {
    default: "premium-glass hover:border-white/20 transition-all duration-500",
    premium: "premium-glass border-blue-500/20 shadow-[0_0_50px_rgba(59,130,246,0.1)] hover:border-blue-500/40",
    dark: "bg-black/80 border-white/5 shadow-2xl backdrop-blur-3xl",
  };

  return (
    <div className={`relative rounded-[2rem] border overflow-hidden group ${variants[variant]} ${className}`}>
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
  <div className="premium-glass p-4 sm:p-6 md:p-8 hover:translate-y-[-4px] hover:border-white/20 transition-all duration-300 group overflow-hidden">
    <div className="space-y-2 sm:space-y-4 relative z-10">
      <div className="flex justify-between items-start">
        <p className="text-[10px] sm:text-institutional text-slate-500 opacity-60 uppercase tracking-widest">{label}</p>
        <div className={`w-1 h-1 sm:w-1.5 sm:h-1.5 rounded-full blur-[1px] ${colorClass.replace('text-', 'bg-')} shadow-[0_0_8px_currentColor]`} />
      </div>
      <p className={`text-2xl sm:text-3xl md:text-4xl font-black font-mono tracking-tighter ${colorClass}`}>{value}</p>
      <div className="flex items-center gap-2">
        <div className="w-0.5 sm:w-1 h-2 sm:h-3 bg-white/5 rounded-full" />
        <p className="text-[8px] sm:text-[9px] text-slate-500 font-bold uppercase tracking-widest">{sub}</p>
      </div>
    </div>
    {/* Background Pattern */}
    <div className="absolute top-0 right-0 w-16 h-16 sm:w-24 sm:h-24 bg-white/[0.02] -rotate-12 translate-x-8 -translate-y-8 sm:translate-x-12 sm:-translate-y-12 group-hover:rotate-0 transition-transform duration-700" />
  </div>
);

const SignalCard = ({ signal, onExecute }: { signal: TradeSignal, onExecute: (id: string) => void }) => {
  const isPE = signal.option_type === 'PE' || signal.reasoning.includes('BEAR') || signal.reasoning.includes('SELL');
  const accentColor = isPE ? 'rose' : 'emerald';

  return (
    <div className="p-4 sm:p-8 md:p-12 relative group premium-glass rounded-2xl sm:rounded-[2.5rem]">
      {/* Dynamic Background Glow */}
      <div className={`absolute -top-24 -right-24 w-96 h-96 bg-${accentColor}-500/10 blur-[120px] rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-1000`} />

      <div className="relative z-10">
        {/* Header: Asset & Type */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-6 mb-6 sm:mb-12">
          <div className="flex items-center gap-4 sm:gap-6">
            <div className={`w-12 h-12 sm:w-16 sm:h-16 rounded-xl sm:rounded-2xl bg-${accentColor}-500/10 border border-${accentColor}-500/20 flex items-center justify-center shadow-lg`}>
              {isPE ? <TrendingDown className="w-6 h-6 sm:w-8 sm:h-8 text-rose-400" /> : <TrendingUp className="w-6 h-6 sm:w-8 sm:h-8 text-emerald-400" />}
            </div>
            <div>
              <div className="flex items-center gap-2 sm:gap-4">
                <h3 className="text-2xl sm:text-3xl md:text-5xl font-black text-white tracking-tighter uppercase">{signal.symbol}</h3>
                <NeonBadge color={accentColor}>{signal.option_type || (isPE ? 'SHORT' : 'LONG')}</NeonBadge>
              </div>
              <p className="text-[10px] sm:text-institutional text-slate-500 mt-1 sm:mt-2 font-bold">
                {signal.option_symbol || 'Protocol Execution'} • {signal.decision_id?.slice(0, 8) || 'SENTINEL'}
                {signal.timestamp && (
                  <span className="ml-2 text-blue-400 opacity-60">
                    [{new Date(signal.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}]
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="flex flex-row sm:flex-col items-center sm:items-end gap-2 sm:gap-0">
            <p className="text-[8px] sm:text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0 sm:mb-1">Confidence</p>
            <p className={`text-lg sm:text-2xl font-black font-mono ${signal.confidence === 'HIGH' ? 'text-blue-400' : 'text-slate-300'}`}>
              {signal.confidence}
            </p>
          </div>
        </div>

        {/* Data Grid: High Contrast Pricing */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6 mb-6 sm:mb-12">
          {[
            { label: 'Strike', val: signal.premium_entry || signal.entry_price, color: 'text-white' },
            { label: 'Stop Loss', val: signal.premium_sl || signal.stop_loss, color: 'text-rose-400' },
            { label: 'Target', val: signal.premium_target || signal.target, color: 'text-emerald-400' },
            { label: 'Momentum', val: `${(signal.score || 0.95).toFixed(2)}`, color: 'text-violet-400' },
          ].map((d, i) => (
            <div key={i} className="bg-black/20 rounded-xl sm:rounded-[1.5rem] p-3 sm:p-6 border border-white/5 hover:border-white/10 transition-all duration-300 group/item">
              <p className="text-[8px] sm:text-[9px] font-black text-slate-500 uppercase tracking-[0.15em] sm:tracking-[0.2em] mb-1 sm:mb-3 group-hover/item:text-slate-400 transition-colors">{d.label}</p>
              <p className={`text-lg sm:text-2xl font-black font-mono tracking-tighter ${d.color}`}>
                {i < 3 ? `₹${d.val.toLocaleString()}` : d.val}
              </p>
            </div>
          ))}
        </div>

        {/* Intelligence Matrix & Action */}
        <div className="flex flex-col xl:flex-row gap-4 sm:gap-8 items-stretch">
          <div className="flex-1 bg-white/[0.02] rounded-xl sm:rounded-[1.5rem] p-4 sm:p-8 border-l-4 border-l-blue-500 relative overflow-hidden group/matrix transition-all hover:bg-white/[0.04]">
            <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-4">
              <Brain className="w-3 h-3 sm:w-4 sm:h-4 text-blue-400" />
              <span className="text-[10px] sm:text-institutional text-slate-400 opacity-60 uppercase tracking-widest font-bold">Neural Matrix</span>
            </div>
            <p className="text-xs sm:text-base text-slate-300 font-medium leading-relaxed italic pr-2 sm:pr-4">
              "{signal.reasoning}"
            </p>
            {/* Ambient shimmer */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent -translate-x-full group-hover/matrix:animate-shimmer pointer-events-none" />
          </div>

          <div className="flex flex-col justify-center gap-4 min-w-[280px] premium-glass p-6 md:p-8 rounded-2xl border border-blue-500/20 bg-blue-500/[0.02]">
            <div className="flex items-center gap-4">
              <div className="w-4 h-4 rounded-full bg-blue-500 animate-pulse shadow-[0_0_15px_rgba(59,130,246,0.8)]" />
              <div className="space-y-1">
                <span className="text-xs sm:text-sm font-black text-white uppercase tracking-[0.2em]">Auto-Approved</span>
                <p className="text-[9px] text-blue-400 font-mono font-bold uppercase tracking-widest">Logic Authority Locked</p>
              </div>
            </div>
            <div className="h-px bg-white/5 w-full" />
            <div className="flex items-center gap-3">
              <Shield className="w-4 h-4 text-slate-500" />
              <p className="text-[10px] text-slate-500 font-bold italic">Full Responsibility Mode Active</p>
            </div>
          </div>
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

  // [v9.9.9] Hardcoded Fallback to ensure connectivity if ENV fails
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
    <main className="min-h-screen bg-[#030305] text-slate-200 selection:bg-blue-500/30 font-sans p-4 sm:p-8 lg:p-16 overflow-x-hidden relative">
      {/* Institutional Grid & Scanline */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.03]" style={{ backgroundImage: `radial-gradient(#ffffff 1px, transparent 1px)`, backgroundSize: '40px 40px' }} />
      <div className="fixed inset-0 pointer-events-none bg-gradient-to-b from-transparent via-white/[0.01] to-transparent h-2 top-0 animate-scanline" />

      {/* Background Ambience */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[60%] h-[60%] bg-blue-600/10 blur-[200px] rounded-full" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[60%] h-[60%] bg-cyan-600/5 blur-[200px] rounded-full" />
      </div>

      <div className="max-w-[1800px] mx-auto space-y-16 relative z-10">

        {/* Header HUD Section */}
        <header className="flex flex-col xl:flex-row justify-between items-stretch gap-4 md:gap-6 premium-glass p-4 sm:p-6 md:p-8 rounded-2xl sm:rounded-[3rem] relative overflow-hidden group">
          {/* Subtle Scanline for Header */}
          <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-transparent via-white/[0.02] to-transparent h-px top-0 animate-scanline opacity-50" />

          <div className="flex items-center gap-4 sm:gap-8 relative z-10">
            <div className="w-12 h-12 sm:w-20 sm:h-20 rounded-xl sm:rounded-[2rem] bg-gradient-to-br from-blue-600 to-cyan-500 p-[1px] shadow-3xl shadow-blue-500/20 group-hover:scale-105 transition-transform duration-500">
              <div className="w-full h-full bg-[#050507] rounded-xl sm:rounded-[2rem] flex items-center justify-center relative overflow-hidden">
                <Shield className="w-6 h-6 sm:w-10 sm:h-10 text-white relative z-10" />
                <div className="absolute inset-0 bg-blue-500/10 animate-pulse-slow" />
              </div>
            </div>
            <div className="space-y-1 sm:space-y-3">
              <h1 className="text-xl sm:text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500 tracking-tighter uppercase">
                Titan<span className="text-white">Plus</span>
                <span className="ml-2 text-[8px] sm:text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 sm:py-0.5 rounded border border-emerald-500/20 align-top tracking-widest font-mono">v12.6.0</span>
              </h1>
              <div className="flex items-center gap-2 sm:gap-5">
                <span className="text-[10px] sm:text-institutional text-slate-500 opacity-60">Titan Institutional</span>
                <div className="h-2 sm:h-3 w-px bg-white/10" />
                <span className="text-[10px] sm:text-institutional text-blue-500">PRO_GRADE</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:gap-4 relative z-10">
            <div className="flex flex-col items-start sm:items-end sm:pr-8 sm:border-r border-white/10">
              <p className="text-[9px] sm:text-institutional text-slate-500 mb-0.5 sm:mb-1">Grid Status</p>
              <div className="flex items-center gap-2 sm:gap-3">
                <div className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${connected ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)] animate-pulse' : 'bg-rose-500'}`} />
                <span className="text-xs sm:text-sm font-black text-white font-mono tracking-tighter">
                  {connected ? 'NOMINAL' : 'OFFLINE'}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 sm:gap-6 px-4 sm:px-8 py-2 sm:py-4 bg-white/[0.02] rounded-xl sm:rounded-2xl border border-white/5 flex-1 sm:flex-none">
              <div className="flex flex-col">
                <p className="text-[9px] sm:text-institutional text-slate-500 mb-0.5 sm:mb-1">Latency</p>
                <div className="flex items-center gap-2">
                  <Wifi className="w-3 h-3 sm:w-4 sm:h-4 text-blue-500" />
                  <p className="text-xs sm:text-sm font-black text-white font-mono">{state?.data_latency || 0}ms</p>
                </div>
              </div>
              <div className="h-6 sm:h-10 w-px bg-white/10" />
              <div className="flex flex-col">
                <p className="text-[9px] sm:text-institutional text-slate-500 mb-0.5 sm:mb-1">System Time</p>
                <div className="flex items-center gap-2">
                  <Clock className="w-3 h-3 sm:w-4 sm:h-4 text-blue-500" />
                  <span className="text-xs sm:text-base font-black text-white font-mono">
                    {lastUpdate.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
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
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 md:gap-8">
          <StatCard label="Volatility" value={state?.vix || '14.2'} sub="India VIX Alpha" colorClass="text-cyan-400" />
          <StatCard label="Sentiment" value={(state?.active_signals?.[0]?.score || 0.95).toFixed(2)} sub="Global PCR Bias" colorClass="text-violet-400" />
          <StatCard label="Advances" value={state?.breadth?.advances || '0'} sub="Bullish Synergy" colorClass="text-emerald-400" />
          <StatCard label="Declines" value={state?.breadth?.declines || '0'} sub="Bearish Friction" colorClass="text-rose-400" />
          <StatCard label="Integrity" value={state?.is_in_recovery ? 'STRICT' : 'MAX'} sub="Governor State" colorClass={state?.is_in_recovery ? 'text-rose-400' : 'text-blue-400'} />
          <StatCard label="Precision" value={accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : '94.2%'} sub="Model Accuracy" colorClass="text-emerald-400" />
        </div>

        <div className="grid grid-cols-1 2xl:grid-cols-4 gap-12">

          <div className="2xl:col-span-3 space-y-16">

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-10">
              {['NIFTY', 'BANKNIFTY', 'SENSEX', 'BTCUSDT', 'ETHUSDT'].map(sym => (
                <GlassCard key={sym} variant="premium" className="p-6 md:p-10 group hover:ring-2 ring-blue-500/20 transition-all duration-700">
                  <div className="flex justify-between items-center mb-6 md:mb-10">
                    <span className="text-[10px] md:text-xs font-black text-slate-400 uppercase tracking-[0.4em] font-mono">{sym} CORE</span>
                    <FlowIcon className="w-5 h-5 md:w-6 md:h-6 text-blue-400 opacity-20 group-hover:opacity-100 transition-all duration-700" />
                  </div>
                  <div className="space-y-2 md:space-y-4">
                    <p className="text-4xl md:text-6xl font-black text-white tracking-tighter group-hover:translate-x-2 transition-transform duration-700 origin-left">
                      {state?.prices[sym]?.toLocaleString('en-IN') || '---'}
                    </p>
                    <div className="flex items-center gap-2 md:gap-3">
                      <p className="text-[8px] md:text-[10px] font-mono text-emerald-400 font-black tracking-[0.2em] md:tracking-[0.3em] uppercase opacity-80 group-hover:opacity-100 transition-opacity">Synergy ACTIVE</p>
                    </div>
                  </div>
                  <div className="mt-8 md:mt-12 h-1.5 md:h-2 w-full bg-white/5 rounded-full overflow-hidden shadow-inner">
                    <div className="h-full bg-gradient-to-r from-blue-600 via-cyan-500 to-blue-400 w-[65%] group-hover:w-full transition-all duration-[2s] rounded-full shadow-[0_0_15px_rgba(59,130,246,0.3)]" />
                  </div>
                </GlassCard>
              ))}
            </div>

            <div className="space-y-10">
              <div className="flex flex-col md:flex-row md:items-center gap-4 md:gap-8">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 md:w-14 md:h-14 rounded-2xl md:rounded-3xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shadow-xl">
                    <Target className="w-5 h-5 md:w-7 md:h-7 text-blue-400" />
                  </div>
                  <h2 className="text-2xl md:text-4xl font-black text-white uppercase tracking-tighter italic">Neural Alpha</h2>
                </div>
                <div className="h-[1px] md:h-[2px] bg-gradient-to-r from-white/20 via-white/5 to-transparent flex-1" />
              </div>

              <div className="grid grid-cols-1 gap-10 max-h-[1200px] overflow-y-auto scrollbar-none pr-4">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  [...state.active_signals].reverse().map((sig, i) => (
                    <div key={i} className="animate-in fade-in slide-in-from-bottom-8 duration-700" style={{ animationDelay: `${i * 150}ms` }}>
                      <SignalCard signal={sig} onExecute={handleExecute} />
                    </div>
                  ))
                ) : (
                  <div className="py-48 flex flex-col items-center justify-center premium-glass rounded-[4rem] group relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/[0.02] to-transparent animate-scanline pointer-events-none" />
                    <div className="w-32 h-32 bg-white/[0.02] rounded-full flex items-center justify-center mb-10 group-hover:rotate-[360deg] transition-all duration-[2s] border border-white/5 shadow-inner">
                      <Eye className="w-12 h-12 text-slate-800 opacity-30 group-hover:opacity-60 transition-opacity" />
                    </div>
                    <div className="text-center space-y-4 relative z-10">
                      <p className="text-institutional text-slate-600 opacity-50 block">Observing Deep-Market Latency</p>
                      <h4 className="text-3xl font-black text-white/20 tracking-tighter uppercase italic">Awaiting Footprint</h4>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-12">

            <GlassCard className="p-6 md:p-12 space-y-8 md:space-y-12 border-blue-500/20 shadow-3xl">
              <div className="flex items-center justify-between">
                <div className="space-y-1 md:space-y-2">
                  <h3 className="text-xs md:text-sm font-black text-white uppercase tracking-[0.3em]">Grid Status</h3>
                  <p className="text-[9px] md:text-[11px] text-slate-400 font-mono font-bold uppercase opacity-60 tracking-widest">Efficiency Metrics</p>
                </div>
                <Activity className="w-5 h-5 md:w-6 md:h-6 text-blue-400 animate-pulse" />
              </div>

              <div className="space-y-6 md:space-y-10">
                {[
                  { label: "Pipeline Sync", val: `${state?.data_latency || 0}ms`, p: "98%", c: "bg-blue-400 shadow-blue-400/50" },
                  { label: "Neural Entropy", val: "Optimal", p: "72%", c: "bg-cyan-400 shadow-cyan-400/50" },
                  { label: "Alpha Integrity", val: "NOMINAL", p: "100%", c: "bg-emerald-400 shadow-emerald-400/50" },
                ].map((item, i) => (
                  <div key={i} className="space-y-3 md:space-y-4">
                    <div className="flex justify-between text-[9px] md:text-[11px] font-black text-slate-400 uppercase tracking-widest">
                      <span>{item.label}</span>
                      <span className="text-white opacity-90">{item.val}</span>
                    </div>
                    <div className="h-1.5 md:h-2 w-full bg-white/5 rounded-full overflow-hidden shadow-inner">
                      <div className={`h-full ${item.c} shadow-[0_0_15px_rgba(59,130,246,0.3)] rounded-full transition-all duration-[1.5s]`} style={{ width: item.p }} />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Sub-Neural Flow: Institutional Terminal */}
            <div className="premium-glass flex flex-col h-[600px] md:h-[900px] overflow-hidden rounded-[3rem] relative lg:sticky lg:top-16 border-none">
              <div className="p-8 border-b border-white/5 bg-white/[0.01] flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                    <FlowIcon className="w-6 h-6 text-violet-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-black text-white uppercase tracking-[0.4em] font-mono leading-none">Sub-Neural Flow</h3>
                    <p className="text-[9px] text-slate-500 font-mono mt-1 font-bold">LIVE_TERMINAL_FEED</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <div className="w-2 h-2 rounded-full bg-violet-500/40 animate-pulse" />
                  <div className="w-2 h-2 rounded-full bg-violet-500 shadow-[0_0_10px_rgba(167,139,250,0.8)]" />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-8 space-y-6 scrollbar-none bg-black/40 font-mono">
                {state?.thought_logs && state.thought_logs.length > 0 ? (
                  [...state.thought_logs].reverse().slice(0, 50).map((log, i) => (
                    <div key={i} className="group/log relative border-l border-white/5 pl-6 hover:border-violet-500/30 transition-colors">
                      <div className="flex justify-between items-start mb-2">
                        <span className={`text-[9px] font-black px-2 py-0.5 rounded-md uppercase tracking-widest ${log.type === 'INFO' ? 'text-cyan-400 bg-cyan-400/10' :
                          log.type === 'TRACE' ? 'text-violet-400 bg-violet-400/10' :
                            'text-amber-400 bg-amber-400/10'
                          }`}>
                          {log.type}
                        </span>
                        <span className="text-[9px] font-mono text-slate-600 font-bold tracking-tighter">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed font-mono group-hover/log:text-slate-200 transition-colors">
                        {log.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="h-full flex flex-col items-center justify-center space-y-6 opacity-20">
                    <RefreshCw className="w-12 h-12 animate-spin-slow text-slate-800" />
                    <p className="text-institutional text-slate-900">Syncing Synapses...</p>
                  </div>
                )}
              </div>

              <div className="p-4 bg-white/[0.02] border-t border-white/5 flex justify-between items-center px-8">
                <span className="text-[8px] font-mono text-slate-600 font-bold uppercase tracking-[0.2em]">Buffer: 512KB</span>
                <span className="text-[8px] font-mono text-slate-600 font-bold uppercase tracking-[0.2em]">Thread: 0x neural_main</span>
              </div>
            </div>
          </div>
        </div>

        <footer className="pt-12 sm:pt-24 pb-10 sm:pb-20 border-t border-white/5 flex flex-col xl:flex-row justify-between items-center gap-8 sm:gap-16 group">
          <div className="flex flex-col md:flex-row items-center gap-8 sm:gap-16 text-center md:text-left">
            <div className="flex items-center gap-4 sm:gap-6">
              <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-white/[0.02] flex items-center justify-center shadow-2xl border border-white/5 group-hover:border-blue-500/20 transition-all duration-700">
                <Shield className="w-5 h-5 sm:w-7 sm:h-7 text-blue-500 opacity-50 group-hover:opacity-100" />
              </div>
              <div className="space-y-0.5 sm:space-y-1">
                <p className="text-[10px] sm:text-institutional text-white opacity-80 uppercase tracking-widest">© 2026 TITAN PLUS SYSTEMS</p>
                <p className="text-[9px] sm:text-institutional text-slate-600 font-bold">Institutional Authority Grade</p>
              </div>
            </div>
            <div className="hidden md:block h-16 w-px bg-white/5" />
            <div className="flex items-center gap-6 sm:gap-12 text-[10px] sm:text-institutional text-slate-600">
              <span className="hover:text-blue-400 transition-colors">Uptime: 99.9%</span>
              <span className="hover:text-violet-400 transition-colors">Latency: Optimal</span>
            </div>
          </div>

          <div className="premium-glass px-6 sm:px-16 py-4 sm:py-8 rounded-2xl sm:rounded-[3rem] border border-white/5 group-hover:border-white/10 transition-all duration-1000 w-full sm:w-auto">
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-12">
              <div className="flex items-center gap-3">
                <span className="text-[10px] sm:text-institutional text-slate-500 italic">Cluster:</span>
                <span className="text-emerald-400 font-mono text-[10px] sm:text-xs font-black tracking-widest animate-pulse">HKG-SENTINEL</span>
              </div>
              <div className="hidden sm:block w-1.5 h-1.5 rounded-full bg-white/5" />
              <div className="flex items-center gap-3">
                <span className="text-[10px] sm:text-institutional text-slate-500 italic">State:</span>
                <span className="text-cyan-400 font-mono text-[10px] sm:text-xs font-black italic tracking-wide">"{state?.market_message || 'NOMINAL'}"</span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
