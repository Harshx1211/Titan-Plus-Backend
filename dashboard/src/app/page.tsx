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
  BarChart2
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
  <div className="flex items-center gap-2">
    {connected ? (
      <>
        <Wifi className="w-4 h-4 text-emerald-500" />
        <span className="text-xs font-mono text-emerald-500 uppercase tracking-wider">
          Live
        </span>
      </>
    ) : (
      <>
        <WifiOff className="w-4 h-4 text-rose-500" />
        <span className="text-xs font-mono text-rose-500 uppercase tracking-wider">
          Disconnected
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
    <span className={`px-3 py-1 rounded-md border text-xs font-mono uppercase tracking-wider ${colors[regime as keyof typeof colors] || colors.UNCERTAIN}`}>
      {regime}
    </span>
  );
};

const ConfidenceMeter: React.FC<{ level: string; value?: number }> = ({ level, value }) => {
  const config = {
    EXTREME: { width: '100%', color: 'bg-emerald-500', glow: 'shadow-emerald-500/50' },
    HIGH: { width: '75%', color: 'bg-cyan-500', glow: 'shadow-cyan-500/50' },
    MEDIUM: { width: '50%', color: 'bg-amber-500', glow: 'shadow-amber-500/50' },
    LOW: { width: '25%', color: 'bg-rose-500', glow: 'shadow-rose-500/50' }
  };

  const conf = config[level as keyof typeof config] || config.LOW;

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
          {level}
        </span>
        {value && (
          <span className="text-xs font-mono text-slate-500">
            {(value * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <div className="h-2 bg-slate-800/50 rounded-full overflow-hidden">
        <div
          className={`h-full ${conf.color} ${conf.glow} shadow-lg transition-all duration-500`}
          style={{ width: conf.width }}
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

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://titan-plus-backend.onrender.com';

  // ========================================================================
  // Data Fetching
  // ========================================================================

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stateRes, historyRes, accRes] = await Promise.all([
          fetch(`${API_URL}/state`),
          fetch(`${API_URL}/history`),
          fetch(`${API_URL}/accuracy`)
        ]);

        if (!stateRes.ok || !historyRes.ok || !accRes.ok) {
          throw new Error('API response error');
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
        console.error('Connection error:', err);
        setConnected(false);
        setLoading(false);
        setError(err instanceof Error ? err.message : 'Connection failed');
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [API_URL]);

  // ========================================================================
  // Computed Metrics
  // ========================================================================

  const metrics = useMemo(() => {
    if (!state) return null;

    const breadthRatio = state.breadth.advances / Math.max(state.breadth.declines, 1);
    const activeCount = state.active_signals?.length || 0;
    const recentThoughts = state.thought_logs?.slice(-5) || [];

    return {
      breadthRatio,
      activeCount,
      recentThoughts,
      isHealthy: connected && !state.is_in_recovery && state.data_latency < 5000
    };
  }, [state, connected]);

  // ========================================================================
  // Trade Execution
  // ========================================================================

  const handleExecuteTrade = async (signalId: string) => {
    try {
      const response = await fetch(`${API_URL}/execute_trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id: signalId })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Execution failed');
      }

      console.log(`Trade ${signalId} executed`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Execution error');
    }
  };

  // ========================================================================
  // Loading State
  // ========================================================================

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4">
        <div className="text-center space-y-6">
          <div className="relative">
            <div className="w-20 h-20 border-4 border-slate-800 border-t-cyan-500 rounded-full animate-spin mx-auto" />
            <div className="absolute inset-0 w-20 h-20 border-4 border-slate-800 border-t-emerald-500 rounded-full animate-spin mx-auto" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
          </div>
          <div className="space-y-2">
            <p className="text-slate-400 font-mono text-sm uppercase tracking-widest">
              Initializing Oracle
            </p>
            <p className="text-slate-600 font-mono text-xs">
              Connecting to BrainEngine v2.0...
            </p>
          </div>
        </div>
      </main>
    );
  }

  // ========================================================================
  // Main Dashboard UI
  // ========================================================================

  return (
    <main className="min-h-screen bg-[#020204] text-[#f8fafc] selection:bg-cyan-500/30">
      {/* Background Gradient Blurs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-cyan-500/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-violet-500/10 blur-[120px] rounded-full" />
      </div>

      {/* Header */}
      <header className="border-b border-white/5 backdrop-blur-2xl bg-black/20 sticky top-0 z-50">
        <div className="max-w-[1920px] mx-auto px-6 py-5">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            {/* Logo & Title */}
            <div className="flex items-center gap-5">
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 via-violet-500 to-emerald-500 rounded-xl blur opacity-25 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
                <div className="relative w-12 h-12 rounded-xl bg-black flex items-center justify-center border border-white/10">
                  <Shield className="w-7 h-7 text-cyan-400" />
                </div>
              </div>
              <div>
                <h1 className="text-2xl font-black tracking-tight bg-gradient-to-r from-white via-slate-300 to-slate-500 bg-clip-text text-transparent">
                  TITAN <span className="text-cyan-500">ORACLE</span>
                </h1>
                <p className="text-[10px] text-slate-500 font-mono uppercase tracking-[0.2em]">
                  Institutional High-Frequency Interface v9.8.5
                </p>
              </div>
            </div>

            {/* Status & Metrics */}
            <div className="flex items-center gap-6 flex-wrap">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
                <StatusBadge connected={connected} />
              </div>

              {state && (
                <>
                  <RegimeBadge regime={state.regime} />

                  <div className="flex items-center gap-3 px-4 py-1.5 rounded-full bg-black/40 border border-white/5 shadow-inner">
                    <Clock className="w-4 h-4 text-cyan-500/70" />
                    <span className="text-xs font-mono text-slate-400 tracking-wider">
                      {lastUpdate.toLocaleTimeString()}
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
        <div className="bg-rose-500/10 border-b border-rose-500/20 px-4 py-3">
          <div className="max-w-[1920px] mx-auto flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <p className="text-sm text-rose-300 font-mono">{error}</p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        {/* Market Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass-card p-6 flex flex-col justify-between group hover:border-cyan-500/50 transition-all duration-500">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-[0.2em] block mb-1">Index Analysis</span>
                <span className="text-3xl font-black text-white tracking-tighter glow-cyan">
                  NIFTY 50
                </span>
              </div>
              <div className="w-12 h-12 rounded-full bg-cyan-500/5 flex items-center justify-center border border-cyan-500/10 group-hover:scale-110 transition-transform">
                <Activity className="w-6 h-6 text-cyan-400" />
              </div>
            </div>
            <div className="flex items-baseline gap-2 mb-4">
              <span className="text-4xl font-mono font-bold text-white">
                {state?.prices?.["NIFTY"] ? state.prices["NIFTY"].toLocaleString('en-IN') : '--'}
              </span>
              <span className="text-xs font-mono text-emerald-400">Live</span>
            </div>
            {state?.supports?.["NIFTY"] && (
              <div className="grid grid-cols-2 gap-4 mt-2 pt-4 border-t border-white/5 font-mono">
                <div>
                  <span className="text-[9px] text-slate-500 uppercase block mb-1">Delta Floor</span>
                  <span className="text-sm text-emerald-400 font-bold">{state.supports["NIFTY"][0]?.toLocaleString('en-IN') || '--'}</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 uppercase block mb-1">Delta Ceiling</span>
                  <span className="text-sm text-rose-400 font-bold">{state.resistances?.["NIFTY"]?.[0]?.toLocaleString('en-IN') || '--'}</span>
                </div>
              </div>
            )}
          </div>

          <div className="glass-card p-6 flex flex-col justify-between group hover:border-violet-500/50 transition-all duration-500">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-[0.2em] block mb-1">Index Analysis</span>
                <span className="text-3xl font-black text-white tracking-tighter glow-violet">
                  SENSEX
                </span>
              </div>
              <div className="w-12 h-12 rounded-full bg-violet-500/5 flex items-center justify-center border border-violet-500/10 group-hover:scale-110 transition-transform">
                <Activity className="w-6 h-6 text-violet-400" />
              </div>
            </div>
            <div className="flex items-baseline gap-2 mb-4">
              <span className="text-4xl font-mono font-bold text-white">
                {state?.prices?.["SENSEX"] ? state.prices["SENSEX"].toLocaleString('en-IN') : '--'}
              </span>
              <span className="text-xs font-mono text-emerald-400">Live</span>
            </div>
            {state?.supports?.["SENSEX"] && (
              <div className="grid grid-cols-2 gap-4 mt-2 pt-4 border-t border-white/5 font-mono">
                <div>
                  <span className="text-[9px] text-slate-500 uppercase block mb-1">Delta Floor</span>
                  <span className="text-sm text-emerald-400 font-bold">{state.supports["SENSEX"][0]?.toLocaleString('en-IN') || '--'}</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 uppercase block mb-1">Delta Ceiling</span>
                  <span className="text-sm text-rose-400 font-bold">{state.resistances?.["SENSEX"]?.[0]?.toLocaleString('en-IN') || '--'}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* VIX Card */}
          <div className="glass-card p-5 group hover:border-amber-500/30 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Variance Index</span>
              <Activity className="w-4 h-4 text-amber-400 group-hover:rotate-12 transition-transform" />
            </div>
            <div className="text-3xl font-black text-white mb-1 font-mono">
              {state?.vix.toFixed(2) || '--'}
            </div>
            <div className="text-[10px] text-slate-500 font-mono uppercase tracking-tight">Market Volatility</div>
          </div>

          {/* Breadth Card */}
          <div className="glass-card p-5 group hover:border-cyan-500/30 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Internal Breadth</span>
              <BarChart3 className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            </div>
            <div className="text-3xl font-black text-white mb-1 font-mono">
              {state ? `${state.breadth.advances}/${state.breadth.declines}` : '--'}
            </div>
            <div className="text-[10px] text-slate-500 font-mono uppercase tracking-tight">
              ADV/DEC Coefficient: {metrics?.breadthRatio.toFixed(2) || '--'}
            </div>
          </div>

          {/* Sector Synergy Card */}
          <div className="glass-card p-5 group hover:border-emerald-500/30 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Sector Synergy</span>
              <Target className="w-4 h-4 text-emerald-400 group-hover:animate-ping transition-all" />
            </div>
            <div className="text-3xl font-black text-white mb-1 font-mono">
              {state?.sector_synergy ? `${(state.sector_synergy * 100).toFixed(0)}%` : '--'}
            </div>
            <div className="text-[10px] text-slate-500 font-mono uppercase tracking-tight">Inter-Index Alignment</div>
          </div>

          {/* Active Signals Card */}
          <div className="glass-card p-5 group hover:border-violet-500/30 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Live Exposures</span>
              <Zap className="w-4 h-4 text-violet-400 group-hover:scale-125 transition-all" />
            </div>
            <div className="text-3xl font-black text-white mb-1 font-mono">
              {metrics?.activeCount || 0}
            </div>
            <div className="text-[10px] text-slate-500 font-mono uppercase tracking-tight">Active Computational Models</div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Left Column: Active Signals */}
          <div className="xl:col-span-2 space-y-6">

            {/* Tactical Execution Board */}
            <div className="glass-card overflow-hidden neural-pulse">
              <div className="px-6 py-5 border-b border-white/5 flex items-center justify-between bg-black/20">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20">
                    <Target className="w-6 h-6 text-cyan-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-black text-white tracking-tight">NEXUS EXECUTION LAYER</h2>
                    <p className="text-[9px] font-mono text-slate-500 uppercase tracking-widest">High-Frequency Decision Matrix</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                  <span className="text-[10px] font-mono text-cyan-400 uppercase">
                    {state?.active_signals?.length || 0} Active Units
                  </span>
                </div>
              </div>

              <div className="divide-y divide-slate-800/50">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((signal, idx) => (
                    <div key={idx} className="p-8 hover:bg-white/[0.02] transition-colors border-b border-white/5 last:border-0 relative overflow-hidden group">
                      {/* Premium Signal Glow */}
                      <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/5 blur-[60px] rounded-full pointer-events-none group-hover:bg-cyan-500/10 transition-all" />

                      {/* Signal Header */}
                      <div className="flex items-start justify-between mb-6">
                        <div className="space-y-2">
                          <div className="flex items-center gap-4">
                            <h3 className="text-2xl font-black text-white tracking-tighter">
                              {signal.symbol}
                            </h3>
                            <div className="px-2 py-0.5 rounded bg-black/50 border border-white/10">
                              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
                                {signal.option_symbol || 'DIRECT_ASSET'}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-4 text-xs font-mono text-slate-500">
                            <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" /> Spot: {signal.entry_price.toFixed(0)}</span>
                            <span className="flex items-center gap-1"><Target className="w-3 h-3" /> Strike: {signal.strike || 'N/A'}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <RegimeBadge regime={signal.regime} />
                          {signal.is_live && (
                            <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-black uppercase tracking-widest border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                              Executing
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Option Premium Prices */}
                      <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="p-4 rounded-xl bg-black/40 border border-white/5">
                          <div className="text-[9px] text-slate-500 font-mono uppercase tracking-widest mb-1">Entry Equilibrium</div>
                          <div className="text-xl font-black text-cyan-400 font-mono">
                            ₹{signal.premium_entry?.toFixed(2) || signal.entry_price.toFixed(2)}
                          </div>
                        </div>
                        <div className="p-4 rounded-xl bg-black/40 border border-white/5">
                          <div className="text-[9px] text-slate-500 font-mono uppercase tracking-widest mb-1">Defense Floor (SL)</div>
                          <div className="text-xl font-black text-rose-400 font-mono">
                            ₹{signal.premium_sl?.toFixed(2) || signal.stop_loss.toFixed(2)}
                          </div>
                        </div>
                        <div className="p-4 rounded-xl bg-black/40 border border-white/5">
                          <div className="text-[9px] text-slate-500 font-mono uppercase tracking-widest mb-1">Objective Ceiling</div>
                          <div className="text-xl font-black text-emerald-400 font-mono">
                            ₹{signal.premium_target?.toFixed(2) || signal.target.toFixed(2)}
                          </div>
                        </div>
                        <div className="p-4 rounded-xl bg-black/40 border border-white/5">
                          <div className="text-[9px] text-slate-500 font-mono uppercase tracking-widest mb-1">Yield Potential</div>
                          <div className="text-xl font-black text-white font-mono">
                            1:{signal.premium_target && signal.premium_entry && signal.premium_sl
                              ? ((signal.premium_target - signal.premium_entry) / (signal.premium_entry - signal.premium_sl)).toFixed(1)
                              : ((signal.target - signal.entry_price) / (signal.entry_price - signal.stop_loss)).toFixed(1)}
                          </div>
                        </div>
                      </div>

                      {/* Reasoning & Metrics */}
                      <div className="flex flex-col lg:flex-row gap-6">
                        <div className="flex-1 bg-black/40 rounded-xl p-5 border border-white/5">
                          <div className="flex items-center gap-2 mb-3">
                            <Binary className="w-4 h-4 text-slate-500" />
                            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Logic Synthesis</span>
                          </div>
                          <p className="text-xs text-slate-300 font-mono leading-relaxed italic">
                            "{signal.reasoning}"
                          </p>
                        </div>

                        <div className="w-full lg:w-64 flex flex-col justify-center space-y-4">
                          <ConfidenceMeter level={signal.confidence} value={signal.confidence_val} />
                          {(signal.mfe || signal.mae) && (
                            <div className="grid grid-cols-2 gap-2">
                              <div className="px-3 py-2 bg-emerald-500/5 rounded-lg border border-emerald-500/10 flex flex-col">
                                <span className="text-[8px] text-slate-500 uppercase">MFE</span>
                                <span className="text-xs font-bold text-emerald-400">+{signal.mfe?.toFixed(1)}</span>
                              </div>
                              <div className="px-3 py-2 bg-rose-500/5 rounded-lg border border-rose-500/10 flex flex-col">
                                <span className="text-[8px] text-slate-500 uppercase">MAE</span>
                                <span className="text-xs font-bold text-rose-400">-{signal.mae?.toFixed(1)}</span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="mt-8 flex gap-3">
                        <button
                          onClick={() => signal.decision_id && handleExecuteTrade(signal.decision_id)}
                          className="flex-1 px-8 py-4 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white font-black text-xs uppercase tracking-[0.2em] rounded-xl transition-all duration-300 shadow-[0_0_20px_rgba(14,165,233,0.3)] hover:shadow-[0_0_30px_rgba(14,165,233,0.5)] flex items-center justify-center gap-3 group"
                        >
                          <Zap className="w-4 h-4 fill-white animate-pulse" />
                          <span>Commit Execution</span>
                        </button>
                        <button className="px-8 py-4 bg-white/5 hover:bg-white/10 text-slate-400 font-black text-xs uppercase tracking-[0.2em] rounded-xl transition-all border border-white/10">
                          Discard
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-24 text-center">
                    <div className="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-6 border border-white/5">
                      <Target className="w-10 h-10 text-slate-700 animate-slow-pulse" />
                    </div>
                    <p className="text-slate-500 font-mono text-xs uppercase tracking-widest">
                      Autonomous Observation in Progress...
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Brain Activity & Metrics */}
          <div className="space-y-6">

            {/* Neural Stream: Epistemic Analysis */}
            <div className="glass-card overflow-hidden h-full flex flex-col">
              <div className="px-6 py-4 border-b border-white/5 flex items-center gap-3 bg-white/[0.02]">
                <div className="relative">
                  <div className="absolute inset-0 bg-violet-500 blur-md opacity-20 animate-pulse" />
                  <Brain className="w-6 h-6 text-violet-400 relative z-10" />
                </div>
                <div>
                  <h2 className="text-sm font-black text-white uppercase tracking-widest">Neural Stream</h2>
                  <p className="text-[8px] font-mono text-slate-500 uppercase">Real-time Epistemic Processing</p>
                </div>
              </div>

              <div className="p-4 space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar">
                {metrics?.recentThoughts && metrics.recentThoughts.length > 0 ? (
                  metrics.recentThoughts.map((thought, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/30 rounded-lg border border-slate-700/30 hover:border-slate-600/50 transition-colors">
                      <div className="flex items-start gap-2 mb-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase tracking-wider ${thought.type === 'INFO' ? 'bg-cyan-500/10 text-cyan-400' :
                          thought.type === 'WARN' ? 'bg-amber-500/10 text-amber-400' :
                            thought.type === 'TRACE' ? 'bg-purple-500/10 text-purple-400' :
                              'bg-rose-500/10 text-rose-400'
                          }`}>
                          {thought.type}
                        </span>
                        <span className="text-xs font-mono text-slate-500">
                          {new Date(thought.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 font-mono leading-relaxed">
                        {thought.msg}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8">
                    <Eye className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    <p className="text-xs text-slate-500 font-mono">
                      Observing market conditions...
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Flow Guardrails */}
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800/50">
                <h2 className="text-lg font-bold text-white">Flow Guardrails</h2>
              </div>

              <div className="p-6 space-y-6">
                {/* IV Skew */}
                {state?.iv_skew && Object.keys(state.iv_skew).length > 0 && (
                  <div>
                    <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-3">
                      IV Skew (Fear/Hedging)
                    </div>
                    {Object.entries(state.iv_skew).map(([asset, skew]) => (
                      <div key={asset} className="mb-3">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-sm font-mono text-slate-300">{asset}</span>
                          <span className={`text-sm font-mono ${skew > 1.3 ? 'text-amber-400' : 'text-emerald-400'}`}>
                            {skew.toFixed(2)}
                          </span>
                        </div>
                        <div className="h-2 bg-slate-800/50 rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ${skew > 1.3 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.min(skew * 50, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* GEX Bias */}
                {state?.gex_bias && Object.keys(state.gex_bias).length > 0 && (
                  <div>
                    <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-3">
                      Gamma Exposure
                    </div>
                    {Object.entries(state.gex_bias).map(([asset, gex]) => (
                      <div key={asset} className="flex items-center justify-between mb-2">
                        <span className="text-sm font-mono text-slate-300">{asset}</span>
                        <span className={`text-sm font-mono ${gex > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {gex > 0 ? '+' : ''}{gex.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* System Health */}
                <div>
                  <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-3">
                    System Health
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">Data Latency</span>
                      <span className={`text-sm font-mono ${state && state.data_latency < 5000 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {state?.data_latency || 0}ms
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">Recovery Mode</span>
                      {state?.is_in_recovery ? (
                        <XCircle className="w-4 h-4 text-rose-400" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">Learning Active</span>
                      {state?.is_learning ? (
                        <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-slate-600" />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Accuracy Card */}
            {accuracy && (
              <div className="bg-gradient-to-br from-cyan-500/10 to-emerald-500/10 backdrop-blur-sm border border-cyan-500/20 rounded-xl p-6">
                <div className="flex items-center gap-3 mb-4">
                  <BarChart2 className="w-6 h-6 text-cyan-400" />
                  <h3 className="text-lg font-bold text-white">Performance</h3>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-slate-400 font-mono mb-1">Accuracy</div>
                    <div className="text-2xl font-bold text-white">
                      {(accuracy.accuracy * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-mono mb-1">Win Rate</div>
                    <div className="text-2xl font-bold text-emerald-400">
                      {accuracy.win_rate ? `${(accuracy.win_rate * 100).toFixed(1)}%` : 'N/A'}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-800/50 pt-6 pb-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500 font-mono">
            <div>
              © 2026 Titan Oracle · BrainEngine v2.0 · All systems operational
            </div>
            <div className="flex items-center gap-4">
              <span>Latency: {state?.data_latency || 0}ms</span>
              <span>·</span>
              <span>Resets: {state?.resets_today || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Custom Scrollbar Styles */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(15, 23, 42, 0.3);
          border-radius: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(71, 85, 105, 0.5);
          border-radius: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(71, 85, 105, 0.7);
        }
      `}</style>
    </main>
  );
}
