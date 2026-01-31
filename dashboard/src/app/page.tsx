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
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800/50 backdrop-blur-xl bg-slate-950/50 sticky top-0 z-50">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            {/* Logo & Title */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">
                  Titan Oracle
                </h1>
                <p className="text-xs text-slate-500 font-mono">
                  BrainEngine v2.0 Command Center
                </p>
              </div>
            </div>

            {/* Status & Metrics */}
            <div className="flex items-center gap-4 flex-wrap">
              <StatusBadge connected={connected} />

              {state && (
                <>
                  <RegimeBadge regime={state.regime} />

                  <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-slate-800/50 border border-slate-700/50">
                    <Clock className="w-4 h-4 text-slate-400" />
                    <span className="text-xs font-mono text-slate-400">
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

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* VIX Card */}
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl p-4 hover:border-slate-700/50 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                VIX
              </span>
              <Activity className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {state?.vix.toFixed(2) || '--'}
            </div>
            <div className="text-xs text-slate-500 font-mono">
              Volatility Index
            </div>
          </div>

          {/* Breadth Card */}
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl p-4 hover:border-slate-700/50 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Breadth
              </span>
              <BarChart3 className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {state ? `${state.breadth.advances}/${state.breadth.declines}` : '--'}
            </div>
            <div className="text-xs text-slate-500 font-mono">
              Adv/Dec Ratio: {metrics?.breadthRatio.toFixed(2) || '--'}
            </div>
          </div>

          {/* Sector Synergy Card */}
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl p-4 hover:border-slate-700/50 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Synergy
              </span>
              <Target className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {state?.sector_synergy ? `${(state.sector_synergy * 100).toFixed(0)}%` : '--'}
            </div>
            <div className="text-xs text-slate-500 font-mono">
              NIFTY-BANK Alignment
            </div>
          </div>

          {/* Active Signals Card */}
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl p-4 hover:border-slate-700/50 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Signals
              </span>
              <Zap className="w-4 h-4 text-violet-400" />
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {metrics?.activeCount || 0}
            </div>
            <div className="text-xs text-slate-500 font-mono">
              Active Positions
            </div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Left Column: Active Signals */}
          <div className="xl:col-span-2 space-y-6">

            {/* Tactical Execution Board */}
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                    <Target className="w-5 h-5 text-cyan-400" />
                  </div>
                  <h2 className="text-lg font-bold text-white">Tactical Execution Board</h2>
                </div>
                <span className="text-xs font-mono text-slate-500">
                  {state?.active_signals?.length || 0} Active
                </span>
              </div>

              <div className="divide-y divide-slate-800/50">
                {state?.active_signals && state.active_signals.length > 0 ? (
                  state.active_signals.map((signal, idx) => (
                    <div key={idx} className="p-6 hover:bg-slate-800/30 transition-colors">
                      {/* Signal Header */}
                      <div className="flex items-start justify-between mb-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-3">
                            <h3 className="text-xl font-bold text-white">
                              {signal.symbol}
                            </h3>
                            {signal.option_symbol && (
                              <span className="text-sm font-mono text-slate-400">
                                {signal.option_symbol}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 font-mono">
                            Index: {signal.entry_price.toFixed(0)} | Strike: {signal.strike || 'N/A'}
                          </p>
                        </div>

                        <div className="flex items-center gap-2">
                          {signal.is_live && (
                            <span className="px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-mono uppercase tracking-wider border border-emerald-500/20">
                              Live
                            </span>
                          )}
                          <RegimeBadge regime={signal.regime} />
                        </div>
                      </div>

                      {/* Option Premium Prices */}
                      <div className="mb-4">
                        <div className="text-xs text-slate-400 font-mono uppercase tracking-wider mb-2">
                          Option Premium
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          <div>
                            <div className="text-xs text-slate-500 font-mono mb-1">Entry</div>
                            <div className="text-lg font-bold text-cyan-400">
                              ₹{signal.premium_entry?.toFixed(2) || signal.entry_price.toFixed(2)}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-slate-500 font-mono mb-1">Stop Loss</div>
                            <div className="text-lg font-bold text-rose-400">
                              ₹{signal.premium_sl?.toFixed(2) || signal.stop_loss.toFixed(2)}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-slate-500 font-mono mb-1">Target</div>
                            <div className="text-lg font-bold text-emerald-400">
                              ₹{signal.premium_target?.toFixed(2) || signal.target.toFixed(2)}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-slate-500 font-mono mb-1">R:R</div>
                            <div className="text-lg font-bold text-white">
                              1:{signal.premium_target && signal.premium_entry && signal.premium_sl
                                ? ((signal.premium_target - signal.premium_entry) / (signal.premium_entry - signal.premium_sl)).toFixed(1)
                                : ((signal.target - signal.entry_price) / (signal.entry_price - signal.stop_loss)).toFixed(1)}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Quality Score */}
                      {signal.confidence_val && (
                        <div className="mb-4 p-3 bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 rounded-lg border border-emerald-500/20">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                              Quality Score
                            </span>
                            <span className="text-lg font-bold text-emerald-400">
                              {(signal.confidence_val * 10).toFixed(1)}/10.0
                            </span>
                          </div>
                          <div className="mt-2 flex items-center gap-1">
                            {[...Array(5)].map((_, i) => (
                              <span key={i} className={`text-lg ${i < Math.floor((signal.confidence_val || 0) * 5) ? 'text-emerald-400' : 'text-slate-700'}`}>
                                ⭐
                              </span>
                            ))}
                            <span className="ml-2 text-xs font-mono text-emerald-400 uppercase">
                              {signal.confidence}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Confidence & Reasoning */}
                      <div className="space-y-3">
                        {!signal.confidence_val && (
                          <ConfidenceMeter
                            level={signal.confidence}
                            value={signal.confidence_val}
                          />
                        )}

                        <div className="bg-slate-800/30 rounded-lg p-3 border border-slate-700/30">
                          <p className="text-xs text-slate-400 font-mono leading-relaxed">
                            {signal.reasoning}
                          </p>
                        </div>

                        {/* Performance Metrics */}
                        {(signal.mfe || signal.mae) && (
                          <div className="flex items-center gap-4 text-xs font-mono">
                            {signal.mfe && (
                              <div className="flex items-center gap-1">
                                <TrendingUp className="w-3 h-3 text-emerald-400" />
                                <span className="text-slate-500">MFE:</span>
                                <span className="text-emerald-400">{signal.mfe.toFixed(2)}</span>
                              </div>
                            )}
                            {signal.mae && (
                              <div className="flex items-center gap-1">
                                <TrendingDown className="w-3 h-3 text-rose-400" />
                                <span className="text-slate-500">MAE:</span>
                                <span className="text-rose-400">{signal.mae.toFixed(2)}</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Action Buttons */}
                      <div className="mt-4 flex gap-2">
                        <button
                          onClick={() => signal.decision_id && handleExecuteTrade(signal.decision_id)}
                          className="flex-1 px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-emerald-500 hover:from-cyan-600 hover:to-emerald-600 text-white font-mono text-sm rounded-lg transition-all duration-200 flex items-center justify-center gap-2 group"
                        >
                          <span>Execute Trade</span>
                          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                        </button>
                        <button
                          className="px-6 py-2.5 bg-slate-800/50 hover:bg-slate-700/50 text-slate-400 hover:text-slate-300 font-mono text-sm rounded-lg transition-all duration-200 border border-slate-700/50"
                        >
                          Skip
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-12 text-center">
                    <div className="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center mx-auto mb-4">
                      <Target className="w-8 h-8 text-slate-600" />
                    </div>
                    <p className="text-slate-500 font-mono text-sm">
                      No active signals. Awaiting market opportunities...
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Brain Activity & Metrics */}
          <div className="space-y-6">

            {/* Epistemic Flow (Brain Thoughts) */}
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800/50 flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-violet-400" />
                </div>
                <h2 className="text-lg font-bold text-white">Epistemic Flow</h2>
              </div>

              <div className="p-4 space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar">
                {metrics?.recentThoughts && metrics.recentThoughts.length > 0 ? (
                  metrics.recentThoughts.map((thought, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/30 rounded-lg border border-slate-700/30 hover:border-slate-600/50 transition-colors">
                      <div className="flex items-start gap-2 mb-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase tracking-wider ${thought.type === 'INFO' ? 'bg-cyan-500/10 text-cyan-400' :
                          thought.type === 'WARN' ? 'bg-amber-500/10 text-amber-400' :
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
