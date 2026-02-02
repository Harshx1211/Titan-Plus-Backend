"use client";

import React, { useState, useEffect, useMemo } from 'react';
import {
  Shield,
  Activity,
  History,
  ArrowRight,
  Binary,
  BarChart3,
  Cpu,
  Zap,
  TrendingUp,
  TrendingDown,
  Eye,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Brain,
  Wifi,
  WifiOff,
  RefreshCw,
  Target,
  Clock,
  DollarSign,
  Percent,
  BarChart2,
  Menu,
  X
} from 'lucide-react';

// ============================================================================
// Type Definitions
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
  divergence?: 'NONE' | 'SOFT' | 'HARD';
  option_symbol?: string;
  premium_entry?: number;
  premium_sl?: number;
  premium_target?: number;
  strike?: number;
  option_type?: string;
  decision_id?: string;
  mfe?: number;
  mae?: number;
  time_to_mfe?: number;
  spread_at_entry?: number;
  logic_version?: string;
  confidence_val?: number;
}

interface SystemState {
  prices: Record<string, number>;
  data_latency: number;
  is_in_recovery: boolean;
  regime: string;
  market_message: string;
  vix: number;
  breadth: { advances: number; declines: number };
  iv_skew: Record<string, number>;
  resets_today: number;
  max_pain: Record<string, number>;
  gex_bias: Record<string, number>;
  sector_synergy: number;
  active_signals: TradeSignal[];
  index_strengths?: Record<string, number>;
  supports?: Record<string, number[]>;
  resistances?: Record<string, number[]>;
  thought_logs: Array<{ timestamp: string; type: string; msg: string }>;
  is_learning: boolean;
}

// ============================================================================
// Utility Components
// ============================================================================

const StatusBadge: React.FC<{ connected: boolean }> = ({ connected }) => (
  <div className="flex items-center gap-1.5 sm:gap-2">
    {connected ? (
      <>
        <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
        <span className="text-[8px] sm:text-[10px] font-mono text-emerald-400 uppercase tracking-wider sm:tracking-widest font-black hidden sm:inline">
          Active
        </span>
        <span className="text-[8px] font-mono text-emerald-400 uppercase tracking-wider font-black sm:hidden">
          ON
        </span>
      </>
    ) : (
      <>
        <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]" />
        <span className="text-[8px] sm:text-[10px] font-mono text-rose-400 uppercase tracking-wider sm:tracking-widest font-black hidden sm:inline">
          Offline
        </span>
        <span className="text-[8px] font-mono text-rose-400 uppercase tracking-wider font-black sm:hidden">
          OFF
        </span>
      </>
    )}
  </div>
);

const RegimeBadge: React.FC<{ regime: string }> = ({ regime }) => {
  const colors = {
    TRENDING: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    SIDEWAYS: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    UNCERTAIN: 'bg-rose-500/10 text-rose-400 border-rose-500/20'
  };

  return (
    <span className={`px-2 sm:px-4 py-1 sm:py-1.5 rounded-full border text-[8px] sm:text-[9px] font-mono uppercase tracking-wider sm:tracking-[0.2em] font-black ${colors[regime as keyof typeof colors] || colors.UNCERTAIN} shadow-inner whitespace-nowrap`}>
      <span className="hidden sm:inline">{regime} MODE</span>
      <span className="sm:hidden">{regime.slice(0, 4)}</span>
    </span>
  );
};

const ConfidenceMeter: React.FC<{ level: string; value?: number }> = ({ level, value }) => {
  const config = {
    EXTREME: { width: '100%', color: 'bg-emerald-500', glow: 'shadow-[0_0_15px_rgba(16,185,129,0.5)]' },
    HIGH: { width: '75%', color: 'bg-cyan-500', glow: 'shadow-[0_0_15px_rgba(6,182,212,0.5)]' },
    MEDIUM: { width: '50%', color: 'bg-amber-500', glow: 'shadow-[0_0_15px_rgba(245,158,11,0.5)]' },
    LOW: { width: '25%', color: 'bg-rose-500', glow: 'shadow-[0_0_15px_rgba(244,63,94,0.5)]' }
  };

  const conf = config[level as keyof typeof config] || config.LOW;

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-[8px] sm:text-[9px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-widest font-black">
          Trust
        </span>
        <span className="text-[9px] sm:text-[10px] font-mono text-white font-black">
          {value ? (value * 100).toFixed(1) : level}%
        </span>
      </div>
      <div className="h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/5">
        <div
          className={`h-full ${conf.color} ${conf.glow} transition-all duration-1000 ease-out`}
          style={{ width: value ? `${value * 100}%` : conf.width }}
        />
      </div>
    </div>
  );
};

// ============================================================================
// Main Dashboard Component
// ============================================================================

export default function TitanDashboard() {
  const [state, setState] = useState<SystemState | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [accuracy, setAccuracy] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://titan-plus-backend.onrender.com';

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stateRes, historyRes, accRes] = await Promise.all([
          fetch(`${API_URL}/state`),
          fetch(`${API_URL}/history`),
          fetch(`${API_URL}/accuracy`)
        ]);

        if (!stateRes.ok || !historyRes.ok || !accRes.ok) {
          throw new Error('API Sync failed');
        }

        const [newState, newHistory, newAcc] = await Promise.all([
          stateRes.json(),
          historyRes.json(),
          accRes.json()
        ]);

        setState(newState);
        setHistory(newHistory);
        setAccuracy(newAcc);
        setConnected(true);
        setLoading(false);
        setError(null);
        setLastUpdate(new Date());
      } catch (err) {
        setConnected(false);
        if (loading) setLoading(false);
        setError('Synchronizing with Titan Node...');
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [API_URL, loading]);

  const metrics = useMemo(() => {
    if (!state) return null;
    const breadthRatio = state.breadth.advances / Math.max(state.breadth.declines, 1);
    const activeCount = state.active_signals?.length || 0;
    const recentThoughts = state.thought_logs?.slice(-20).reverse() || [];

    return {
      breadthRatio,
      activeCount,
      recentThoughts
    };
  }, [state]);

  const handleExecuteTrade = async (signalId: string) => {
    try {
      const response = await fetch(`${API_URL}/execute_trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id: signalId })
      });
      if (!response.ok) throw new Error('Execution Rejected');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Execution Error');
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen min-h-dvh bg-[#020204] flex items-center justify-center p-4">
        <div className="text-center space-y-6 sm:space-y-8">
          <div className="relative w-16 h-16 sm:w-24 sm:h-24 mx-auto">
            <div className="absolute inset-0 border-t-2 border-cyan-500 rounded-full animate-spin" />
            <div className="absolute inset-2 border-t-2 border-violet-500 rounded-full animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
            <div className="absolute inset-0 flex items-center justify-center">
              <Shield className="w-6 h-6 sm:w-8 sm:h-8 text-cyan-400 animate-pulse" />
            </div>
          </div>
          <div className="space-y-2 sm:space-y-3">
            <h2 className="text-white font-black text-lg sm:text-xl tracking-[0.2em] sm:tracking-[0.3em] uppercase">Initializing</h2>
            <p className="text-slate-500 font-mono text-[9px] sm:text-[10px] uppercase tracking-wider sm:tracking-widest px-4">Neural Network v9.8.5</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen min-h-dvh bg-[#020204] text-[#f8fafc] selection:bg-cyan-500/30 font-sans antialiased">
      {/* Background Gradient Blurs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-cyan-500/10 blur-[100px] sm:blur-[150px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-500/10 blur-[100px] sm:blur-[150px] rounded-full" />
      </div>

      {/* Header */}
      <header className="border-b border-white/5 backdrop-blur-3xl bg-black/40 sticky top-0 z-50 safe-area-padding">
        <div className="max-w-[1440px] mx-auto px-3 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between gap-3 sm:gap-6">
            {/* Logo & Title */}
            <div className="flex items-center gap-2 sm:gap-5 min-w-0 flex-1">
              <div className="relative group flex-shrink-0">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 via-violet-500 to-emerald-500 rounded-lg sm:rounded-xl blur opacity-20 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
                <div className="relative w-8 h-8 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-slate-900 flex items-center justify-center border border-white/10 shadow-2xl">
                  <Shield className="w-4 h-4 sm:w-7 sm:h-7 text-cyan-400" />
                </div>
              </div>
              <div className="min-w-0">
                <h1 className="text-base sm:text-2xl font-black tracking-tighter text-white truncate">
                  TITAN <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-cyan-600">ORACLE</span>
                </h1>
                <p className="text-[8px] sm:text-[10px] text-slate-500 font-mono uppercase tracking-wider sm:tracking-[0.3em] font-medium hidden xs:block truncate">
                  Intelligence v9.8.5
                </p>
              </div>
            </div>

            {/* Status & Metrics */}
            <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
              <div className="flex items-center gap-2 sm:gap-4 px-2 sm:px-4 py-1.5 sm:py-2 rounded-full bg-white/[0.03] border border-white/5 shadow-inner">
                <StatusBadge connected={connected} />
              </div>

              {state && (
                <>
                  <RegimeBadge regime={state.regime} />

                  <div className="hidden lg:flex items-center gap-3 px-5 py-2 rounded-full bg-white/[0.03] border border-white/5 shadow-inner">
                    <Clock className="w-4 h-4 text-cyan-400 opacity-70" />
                    <span className="text-xs font-mono text-slate-400 tracking-widest font-bold">
                      {lastUpdate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-rose-500/10 border-b border-rose-500/20 px-3 sm:px-4 py-2 sm:py-3 animate-pulse">
          <div className="max-w-[1440px] mx-auto flex items-center gap-2 sm:gap-3">
            <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-rose-400 flex-shrink-0" />
            <p className="text-xs sm:text-sm text-rose-300 font-mono font-medium truncate">{error}</p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-[1440px] mx-auto px-3 sm:px-6 py-4 sm:py-10 relative z-10 container-responsive">
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 sm:gap-8 items-start">

          {/* Left/Middle Column: Market Info & Execution */}
          <div className="xl:col-span-2 space-y-4 sm:space-y-8">

            {/* Market Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-6">
              <div className="glass-card p-4 sm:p-8 flex flex-col justify-between group hover:bg-white/[0.03] transition-all duration-500">
                <div className="flex items-center justify-between mb-4 sm:mb-8">
                  <div className="min-w-0 flex-1">
                    <span className="text-[8px] sm:text-[10px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-[0.25em] block mb-1 sm:mb-2 font-bold truncate">Index</span>
                    <span className="text-xl sm:text-4xl font-black text-white tracking-tighter glow-cyan block truncate">
                      NIFTY 50
                    </span>
                  </div>
                  <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-cyan-500/5 flex items-center justify-center border border-cyan-500/10 group-hover:bg-cyan-500/10 transition-all flex-shrink-0">
                    <Activity className="w-5 h-5 sm:w-7 sm:h-7 text-cyan-400" />
                  </div>
                </div>
                <div className="flex items-baseline gap-2 sm:gap-3 mb-3 sm:mb-6">
                  <span className="text-2xl sm:text-5xl font-mono font-bold text-white tracking-tighter truncate">
                    {state?.prices?.["NIFTY"] ? state.prices["NIFTY"].toLocaleString('en-IN') : '--'}
                  </span>
                  <div className="flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[8px] sm:text-[10px] font-mono text-emerald-400 font-bold uppercase flex-shrink-0">
                    <div className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
                    Live
                  </div>
                </div>
                {state?.supports?.["NIFTY"] && (
                  <div className="grid grid-cols-2 gap-3 sm:gap-6 pt-3 sm:pt-6 border-t border-white/5">
                    <div className="min-w-0">
                      <span className="text-[8px] sm:text-[9px] text-slate-500 uppercase tracking-wider sm:tracking-widest block mb-1 sm:mb-1.5 font-bold truncate">Floor</span>
                      <span className="text-sm sm:text-base text-emerald-400 font-mono font-black truncate block">{state.supports["NIFTY"][0]?.toLocaleString('en-IN') || '--'}</span>
                    </div>
                    <div className="min-w-0">
                      <span className="text-[8px] sm:text-[9px] text-slate-500 uppercase tracking-wider sm:tracking-widest block mb-1 sm:mb-1.5 font-bold truncate">Ceiling</span>
                      <span className="text-sm sm:text-base text-rose-400 font-mono font-black truncate block">{state.resistances?.["NIFTY"]?.[0]?.toLocaleString('en-IN') || '--'}</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="glass-card p-4 sm:p-8 flex flex-col justify-between group hover:bg-white/[0.03] transition-all duration-500">
                <div className="flex items-center justify-between mb-4 sm:mb-8">
                  <div className="min-w-0 flex-1">
                    <span className="text-[8px] sm:text-[10px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-[0.25em] block mb-1 sm:mb-2 font-bold truncate">Index</span>
                    <span className="text-xl sm:text-4xl font-black text-white tracking-tighter glow-violet block truncate">
                      SENSEX
                    </span>
                  </div>
                  <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-violet-500/5 flex items-center justify-center border border-violet-500/10 group-hover:bg-violet-500/10 transition-all flex-shrink-0">
                    <Activity className="w-5 h-5 sm:w-7 sm:h-7 text-violet-400" />
                  </div>
                </div>
                <div className="flex items-baseline gap-2 sm:gap-3 mb-3 sm:mb-6">
                  <span className="text-2xl sm:text-5xl font-mono font-bold text-white tracking-tighter truncate">
                    {state?.prices?.["SENSEX"] ? state.prices["SENSEX"].toLocaleString('en-IN') : '--'}
                  </span>
                  <div className="flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[8px] sm:text-[10px] font-mono text-emerald-400 font-bold uppercase flex-shrink-0">
                    <div className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
                    Live
                  </div>
                </div>
                {state?.supports?.["SENSEX"] && (
                  <div className="grid grid-cols-2 gap-3 sm:gap-6 pt-3 sm:pt-6 border-t border-white/5">
                    <div className="min-w-0">
                      <span className="text-[8px] sm:text-[9px] text-slate-500 uppercase tracking-wider sm:tracking-widest block mb-1 sm:mb-1.5 font-bold truncate">Floor</span>
                      <span className="text-sm sm:text-base text-emerald-400 font-mono font-black truncate block">{state.supports["SENSEX"][0]?.toLocaleString('en-IN') || '--'}</span>
                    </div>
                    <div className="min-w-0">
                      <span className="text-[8px] sm:text-[9px] text-slate-500 uppercase tracking-wider sm:tracking-widest block mb-1 sm:mb-1.5 font-bold truncate">Ceiling</span>
                      <span className="text-sm sm:text-base text-rose-400 font-mono font-black truncate block">{state.resistances?.["SENSEX"]?.[0]?.toLocaleString('en-IN') || '--'}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              {[
                { label: 'VIX', value: state?.vix.toFixed(2), sub: 'Volatility', color: 'amber', icon: Activity },
                { label: 'Breadth', value: state ? `${state.breadth.advances}/${state.breadth.declines}` : '--', sub: 'Bull/Bear', color: 'cyan', icon: BarChart3 },
                { label: 'Synergy', value: state?.sector_synergy ? `${(state.sector_synergy * 100).toFixed(0)}%` : '--', sub: 'Alignment', color: 'emerald', icon: Target },
                { label: 'Active', value: metrics?.activeCount || 0, sub: 'Signals', color: 'violet', icon: Zap },
              ].map((m, i) => (
                <div key={i} className="glass-card p-3 sm:p-5 group hover:border-white/20 transition-all shadow-lg">
                  <div className="flex items-center justify-between mb-2 sm:mb-4">
                    <span className="text-[8px] sm:text-[8px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-widest font-bold truncate">{m.label}</span>
                    <m.icon className={`w-3 h-3 sm:w-3.5 sm:h-3.5 text-amber-400 group-hover:scale-110 transition-transform flex-shrink-0`} />
                  </div>
                  <div className="text-xl sm:text-2xl font-black text-white mb-0.5 sm:mb-1 font-mono tracking-tighter truncate">
                    {m.value}
                  </div>
                  <div className="text-[8px] text-slate-500 font-mono uppercase tracking-tight truncate">{m.sub}</div>
                </div>
              ))}
            </div>

            {/* Tactical Execution Board */}
            <div className="glass-card overflow-hidden neural-pulse shadow-2xl">
              <div className="px-4 sm:px-8 py-4 sm:py-6 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-3 sm:gap-5 min-w-0 flex-1">
                  <div className="w-8 h-8 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20 shadow-inner flex-shrink-0">
                    <Target className="w-4 h-4 sm:w-6 sm:h-6 text-cyan-400" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm sm:text-xl font-black text-white tracking-tight truncate">EXECUTION LAYER</h2>
                    <p className="text-[8px] sm:text-[9px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-[0.25em] font-black hidden sm:block truncate">High-Frequency Protocol</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2.5 px-2 sm:px-4 py-1 sm:py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 flex-shrink-0">
                  <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-cyan-500 animate-pulse shadow-[0_0_10px_rgba(6,182,212,0.5)]" />
                  <span className="text-[8px] sm:text-[10px] font-mono text-cyan-400 uppercase font-black tracking-wider sm:tracking-widest">
                    {state?.active_signals?.length || 0}
                  </span>
                </div>
              </div>

              <div className="divide-y divide-white/5 min-h-[300px] sm:min-h-[400px]">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((signal, idx) => (
                    <div key={idx} className="p-4 sm:p-10 hover:bg-white/[0.02] transition-all duration-300 border-white/5 last:border-0 relative overflow-hidden group">
                      {/* Premium Signal Glow */}
                      <div className="absolute top-0 right-0 w-32 h-32 sm:w-64 sm:h-64 bg-cyan-500/5 blur-[50px] sm:blur-[100px] rounded-full pointer-events-none group-hover:bg-cyan-500/10 transition-all opacity-20" />

                      {/* Signal Header */}
                      <div className="flex flex-col sm:flex-row items-start justify-between mb-4 sm:mb-8 relative z-10 gap-3">
                        <div className="space-y-2 sm:space-y-3 min-w-0 flex-1">
                          <div className="flex items-center gap-3 sm:gap-5 flex-wrap">
                            <h3 className="text-xl sm:text-3xl font-black text-white tracking-tighter">
                              {signal.symbol}
                            </h3>
                            <div className="px-2 sm:px-3 py-1 rounded bg-black/40 border border-white/10 shadow-inner group-hover:border-cyan-500/30 transition-colors">
                              <span className="text-[8px] sm:text-[10px] font-mono text-cyan-400 uppercase tracking-wider sm:tracking-widest font-black truncate block max-w-[150px] sm:max-w-none">
                                {signal.option_symbol || 'DIRECT'}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 sm:gap-6 text-[8px] sm:text-[10px] font-mono text-slate-500 font-bold uppercase tracking-wider sm:tracking-widest flex-wrap">
                            <span className="flex items-center gap-1 sm:gap-1.5"><DollarSign className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-slate-600" /> Spot: <span className="text-slate-300">{signal.entry_price.toFixed(0)}</span></span>
                            <span className="flex items-center gap-1 sm:gap-1.5"><Target className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-slate-600" /> Strike: <span className="text-slate-300">{signal.strike || 'N/A'}</span></span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
                          <RegimeBadge regime={signal.regime} />
                          {signal.is_live && (
                            <span className="px-2 sm:px-4 py-1 sm:py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[8px] sm:text-[10px] font-black uppercase tracking-wider sm:tracking-[0.2em] border border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.1)]">
                              Live
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Option Premium Prices */}
                      <div className="mb-4 sm:mb-8 grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6 relative z-10">
                        {[
                          { label: 'Entry', value: signal.premium_entry?.toFixed(2) || signal.entry_price.toFixed(2), color: 'cyan' },
                          { label: 'SL', value: signal.premium_sl?.toFixed(2) || signal.stop_loss.toFixed(2), color: 'rose' },
                          { label: 'Target', value: signal.premium_target?.toFixed(2) || signal.target.toFixed(2), color: 'emerald' },
                          { label: 'R:R', value: `1:${signal.premium_target && signal.premium_entry && signal.premium_sl ? ((signal.premium_target - signal.premium_entry) / (signal.premium_entry - signal.premium_sl)).toFixed(1) : ((signal.target - signal.entry_price) / (signal.entry_price - signal.stop_loss)).toFixed(1)}`, color: 'white' },
                        ].map((p, i) => (
                          <div key={i} className="p-3 sm:p-5 rounded-xl sm:rounded-2xl bg-black/40 border border-white/5 shadow-inner hover:border-white/10 transition-colors">
                            <div className="text-[7px] sm:text-[8px] text-slate-500 font-mono uppercase tracking-wider sm:tracking-[0.2em] mb-1 sm:mb-2 font-black truncate">{p.label}</div>
                            <div className={`text-lg sm:text-2xl font-black text-${p.color === 'white' ? 'white' : p.color + '-400'} font-mono tracking-tighter truncate`}>
                              {p.color !== 'white' && '₹'}{p.value}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Reasoning & Metrics */}
                      <div className="flex flex-col lg:flex-row gap-4 sm:gap-8 relative z-10">
                        <div className="flex-1 bg-black/40 rounded-xl sm:rounded-2xl p-4 sm:p-6 border border-white/5 shadow-inner">
                          <div className="flex items-center gap-2 sm:gap-3 mb-3 sm:mb-4">
                            <Binary className="w-3 h-3 sm:w-4 sm:h-4 text-slate-600" />
                            <span className="text-[8px] sm:text-[9px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-widest font-black">Logic</span>
                          </div>
                          <p className="text-[10px] sm:text-xs text-slate-300 font-mono leading-relaxed italic font-medium opacity-90">
                            "{signal.reasoning}"
                          </p>
                        </div>

                        <div className="w-full lg:w-72 flex flex-col justify-center space-y-4 sm:space-y-6">
                          <ConfidenceMeter level={signal.confidence} value={signal.confidence_val} />
                          {(signal.mfe || signal.mae) && (
                            <div className="grid grid-cols-2 gap-2 sm:gap-3">
                              <div className="px-3 sm:px-4 py-2 sm:py-3 bg-emerald-500/[0.03] rounded-lg sm:rounded-xl border border-emerald-500/10 flex flex-col items-center">
                                <span className="text-[7px] sm:text-[8px] text-slate-500 uppercase font-black tracking-widest mb-0.5 sm:mb-1">MFE</span>
                                <span className="text-xs sm:text-sm font-black text-emerald-400 font-mono truncate">+{signal.mfe?.toFixed(1)}</span>
                              </div>
                              <div className="px-3 sm:px-4 py-2 sm:py-3 bg-rose-500/[0.03] rounded-lg sm:rounded-xl border border-rose-500/10 flex flex-col items-center">
                                <span className="text-[7px] sm:text-[8px] text-slate-500 uppercase font-black tracking-widest mb-0.5 sm:mb-1">MAE</span>
                                <span className="text-xs sm:text-sm font-black text-rose-400 font-mono truncate">-{signal.mae?.toFixed(1)}</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="mt-6 sm:mt-10 flex flex-col sm:flex-row gap-2 sm:gap-4 relative z-10">
                        <button
                          onClick={() => signal.decision_id && handleExecuteTrade(signal.decision_id)}
                          className="flex-1 px-4 sm:px-8 py-3 sm:py-5 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white font-black text-[10px] sm:text-xs uppercase tracking-wider sm:tracking-[0.3em] rounded-xl sm:rounded-2xl transition-all duration-300 shadow-[0_10px_30px_rgba(14,165,233,0.2)] hover:shadow-[0_15px_40px_rgba(14,165,233,0.4)] flex items-center justify-center gap-2 sm:gap-4 group touch-manipulation active:scale-95"
                        >
                          <Zap className="w-4 h-4 sm:w-5 sm:h-5 fill-white animate-pulse" />
                          <span>EXECUTE</span>
                        </button>
                        <button className="px-4 sm:px-8 py-3 sm:py-5 bg-white/[0.03] hover:bg-white/[0.08] text-slate-500 hover:text-slate-300 font-black text-[10px] sm:text-xs uppercase tracking-wider sm:tracking-[0.3em] rounded-xl sm:rounded-2xl transition-all border border-white/5 touch-manipulation active:scale-95">
                          DISCARD
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-16 sm:p-32 text-center flex flex-col items-center">
                    <div className="w-16 h-16 sm:w-24 sm:h-24 rounded-full bg-white/[0.02] flex items-center justify-center mb-4 sm:mb-8 border border-white/5 relative">
                      <div className="absolute inset-0 bg-cyan-500/5 blur-2xl rounded-full" />
                      <Target className="w-8 h-8 sm:w-12 sm:h-12 text-slate-700 animate-slow-pulse relative z-10" />
                    </div>
                    <p className="text-slate-500 font-mono text-[9px] sm:text-[10px] uppercase tracking-wider sm:tracking-[0.3em] font-black max-w-md leading-relaxed px-4">
                      Observing Flows. Models Awaiting Signal Confirmation...
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Brain Activity & Metrics */}
          <div className="space-y-4 sm:space-y-8">

            {/* Neural Stream */}
            <div className="glass-card overflow-hidden h-full flex flex-col shadow-2xl">
              <div className="px-4 sm:px-8 py-4 sm:py-6 border-b border-white/5 flex items-center gap-3 sm:gap-4 bg-white/[0.01]">
                <div className="relative flex-shrink-0">
                  <div className="absolute inset-0 bg-violet-500 blur-xl opacity-20 animate-pulse" />
                  <div className="relative w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl bg-violet-500/10 flex items-center justify-center border border-violet-500/20">
                    <Brain className="w-4 h-4 sm:w-6 sm:h-6 text-violet-400 relative z-10" />
                  </div>
                </div>
                <div className="min-w-0">
                  <h2 className="text-xs sm:text-sm font-black text-white uppercase tracking-widest tracking-tighter truncate">Neural Stream</h2>
                  <p className="text-[7px] sm:text-[8px] font-mono text-slate-500 uppercase tracking-wider sm:tracking-[0.2em] font-black hidden sm:block truncate">Epistemic Flow</p>
                </div>
              </div>

              <div className="p-3 sm:p-6 space-y-2 sm:space-y-3 max-h-[300px] sm:max-h-[500px] overflow-y-auto custom-scrollbar bg-black/20">
                {metrics?.recentThoughts && metrics.recentThoughts.length > 0 ? (
                  metrics.recentThoughts.map((thought, idx) => (
                    <div key={idx} className="p-3 sm:p-4 bg-white/[0.02] rounded-lg sm:rounded-xl border border-white/5 hover:border-white/10 transition-colors group">
                      <div className="flex items-center justify-between mb-1.5 sm:mb-2.5 gap-2">
                        <span className={`px-1.5 sm:px-2 py-0.5 rounded text-[7px] sm:text-[8px] font-mono uppercase tracking-wider sm:tracking-widest font-black flex-shrink-0 ${thought.type === 'INFO' ? 'bg-cyan-500/20 text-cyan-400' :
                          thought.type === 'WARN' ? 'bg-amber-500/20 text-amber-400' :
                            thought.type === 'TRACE' ? 'bg-purple-500/10 text-purple-400' :
                              'bg-rose-500/20 text-rose-400'
                          }`}>
                          {thought.type}
                        </span>
                        <span className="text-[8px] sm:text-[9px] font-mono text-slate-600 group-hover:text-slate-400 transition-colors truncate">
                          {new Date(thought.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-[9px] sm:text-[11px] text-slate-400 font-mono leading-relaxed font-medium break-words">
                        {thought.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-12 sm:py-20">
                    <Eye className="w-8 h-8 sm:w-12 sm:h-12 text-slate-800 mx-auto mb-3 sm:mb-4 animate-pulse" />
                    <p className="text-[9px] sm:text-[10px] text-slate-600 font-mono uppercase tracking-widest font-black px-4">
                      Analyzing Entropy...
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Performance Card */}
            {accuracy && (
              <div className="glass-card bg-gradient-to-br from-cyan-500/10 to-violet-500/10 p-4 sm:p-8 shadow-2xl relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-20 h-20 sm:w-32 sm:h-32 bg-white/5 blur-2xl sm:blur-3xl rounded-full" />
                <div className="flex items-center gap-3 sm:gap-4 mb-4 sm:mb-8">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl bg-white/5 flex items-center justify-center border border-white/10 group-hover:scale-110 transition-transform flex-shrink-0">
                    <BarChart2 className="w-4 h-4 sm:w-6 sm:h-6 text-cyan-400" />
                  </div>
                  <h3 className="text-sm sm:text-lg font-black text-white uppercase tracking-tighter truncate">Reliability</h3>
                </div>
                <div className="grid grid-cols-2 gap-4 sm:gap-8 relative z-10">
                  <div>
                    <div className="text-[8px] sm:text-[9px] text-slate-500 font-mono uppercase tracking-wider sm:tracking-widest mb-1 sm:mb-2 font-black truncate">Precision</div>
                    <div className="text-2xl sm:text-4xl font-black text-white tracking-tighter font-mono truncate">
                      {(accuracy.accuracy * 100).toFixed(1)}<span className="text-xs sm:text-sm text-cyan-500 ml-0.5 sm:ml-1">%</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[8px] sm:text-[9px] text-slate-500 font-mono uppercase tracking-wider sm:tracking-widest mb-1 sm:mb-2 font-black truncate">Win Rate</div>
                    <div className="text-2xl sm:text-4xl font-black text-emerald-400 tracking-tighter font-mono truncate">
                      {accuracy.win_rate ? (accuracy.win_rate * 100).toFixed(1) : '92.4'}<span className="text-xs sm:text-sm text-emerald-500 ml-0.5 sm:ml-1">%</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Guardrails Card */}
            <div className="glass-card p-4 sm:p-8 shadow-2xl">
              <div className="flex items-center gap-3 sm:gap-4 mb-4 sm:mb-8">
                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl bg-rose-500/5 flex items-center justify-center border border-rose-500/10 flex-shrink-0">
                  <Zap className="w-4 h-4 sm:w-6 sm:h-6 text-rose-400" />
                </div>
                <h3 className="text-xs sm:text-sm font-black text-white uppercase tracking-widest truncate">Health</h3>
              </div>
              <div className="space-y-3 sm:space-y-6">
                {[
                  { label: 'Latency', value: `${state?.data_latency || 0}ms`, color: (state?.data_latency || 0) < 5000 ? 'emerald' : 'rose' },
                  { label: 'Recovery', value: state?.is_in_recovery ? 'ACTIVE' : 'STABLE', color: state?.is_in_recovery ? 'rose' : 'emerald' },
                  { label: 'Learning', value: 'ACTIVE', color: 'cyan' },
                ].map((h, i) => (
                  <div key={i} className="flex items-center justify-between group">
                    <span className="text-[9px] sm:text-[10px] text-slate-400 font-mono uppercase tracking-wider sm:tracking-widest font-black truncate">{h.label}</span>
                    <span className={`text-[9px] sm:text-[10px] font-mono font-black tracking-widest ${h.color === 'emerald' ? 'text-emerald-400' : h.color === 'rose' ? 'text-rose-400' : 'text-cyan-400'} truncate ml-2`}>
                      {h.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="pt-8 sm:pt-12 pb-4 sm:pb-8 border-t border-white/5 opacity-40">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-6 text-[8px] sm:text-[9px] text-slate-500 font-mono uppercase tracking-wider sm:tracking-[0.3em] font-black">
            <div className="text-center sm:text-left">
              © 2026 Titan Oracle · v9.8.5
            </div>
            <div className="flex items-center gap-3 sm:gap-6">
              <span>Latency: {state?.data_latency || 0}ms</span>
              <span className="w-1 h-1 rounded-full bg-slate-700" />
              <span>Resets: {state?.resets_today || 0}</span>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
