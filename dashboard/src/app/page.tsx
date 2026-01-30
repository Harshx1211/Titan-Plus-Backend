"use client";

import React, { useState, useEffect } from 'react';
import {
  Shield,
  Activity,
  History,
  ArrowRight,
  Binary,
  BarChart3,
  Cpu,
  Unplug,
  Zap,
  LayoutGrid,
  Lock,
  Target,
  Eye,
  Crosshair
} from 'lucide-react';

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
  active_signals: any[];
  index_strengths?: Record<string, number>;
  thought_logs: Array<{ timestamp: string; type: string; msg: string }>;
  is_learning: boolean;
}

export default function Home() {
  const [state, setState] = useState<SystemState | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [accuracy, setAccuracy] = useState<any>(null);
  const [activeAsset, setActiveAsset] = useState<'NIFTY' | 'SENSEX'>('NIFTY');
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);  // FIX #5: Add loading state

  useEffect(() => {
    const fetchData = async () => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://titan-plus-backend.onrender.com';
        const [stateRes, historyRes, accRes] = await Promise.all([
          fetch(`${API_URL}/state`),
          fetch(`${API_URL}/history`),
          fetch(`${API_URL}/accuracy`)
        ]);

        const newState = await stateRes.json();
        const newHistory = await historyRes.json();
        const newAcc = await accRes.json();

        setState(newState);
        setHistory(newHistory);
        setAccuracy(newAcc);
        setConnected(true);
        setLoading(false);  // FIX #5: Set loading to false after first fetch
      } catch (err) {
        console.error("Link Failure:", err);
        setConnected(false);
        setLoading(false);  // FIX #5: Set loading to false even on error
      }
    };

    const interval = setInterval(fetchData, 2000);
    fetchData();
    return () => clearInterval(interval);
  }, []);

  // Recovery Mode disabled - User has full control
  // const isRecovering = state?.is_in_recovery;

  // FIX #5: Show loading state
  if (loading) {
    return (
      <main className="min-h-screen bg-[#010103] flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-500 font-mono text-sm uppercase tracking-widest">Initializing Oracle...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen selection:bg-cyan-500/30 overflow-hidden flex flex-col">

      {/* Top Meta-Ticker (Status Bar) */}
      <div className="ticker-wrap h-8 flex items-center justify-between px-4 bg-black/60 backdrop-blur-md z-40 border-b border-white/[0.03]">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className={`status-dot ${connected ? 'text-emerald-500' : 'text-rose-500 animate-slow-pulse'}`} />
            <span className="text-[10px] font-mono font-black uppercase tracking-widest text-slate-500">
              {connected ? 'Sync: Nominal' : 'Sync: Lost'}
            </span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-mono text-slate-600 font-bold uppercase tracking-widest border-l border-white/[0.05] pl-6">
            <LayoutGrid className="w-3 h-3" />
            <span>Terminal: 002-X</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="hidden md:flex items-center gap-3">
            <span className="text-[10px] font-mono text-slate-600 font-bold uppercase tracking-tighter">VIX:</span>
            <span className="text-[10px] font-mono text-amber-500 font-black tracking-tighter">
              {state?.market_message === 'MARKET_CLOSED' || state?.vix === 0 ? '-' : state?.vix?.toFixed(2) || '--.--'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-slate-500 font-black">{state?.data_latency?.toFixed(0) || '0'}ms</span>
            <Unplug className="w-3 h-3 text-slate-700" />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="p-4 md:p-6 lg:p-10 max-w-[1900px] mx-auto space-y-6">

          {/* Header Area */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 border-b border-white/[0.03] pb-6">
            <div className="flex items-center gap-4">
              <div className="bg-cyan-500/10 p-2.5 rounded-xs border border-cyan-500/20">
                <Cpu className="text-cyan-400 w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <h1 className="text-lg font-black tracking-[0.2em] uppercase text-white leading-none">The Oracle</h1>
                <span className="text-[9px] font-mono text-slate-600 font-bold tracking-widest mt-1">Institutional Flow Interface</span>
              </div>
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto">
              {['NIFTY', 'SENSEX'].map((s) => (
                <button
                  key={s}
                  onClick={() => setActiveAsset(s as any)}
                  className={`flex-1 md:flex-none flex flex-col justify-center px-6 py-2 border transition-all ${activeAsset === s ? 'border-cyan-500/30 bg-cyan-500/5' : 'border-white/5 opacity-50 hover:opacity-100 hover:bg-white/5'}`}
                >
                  <span className="text-[9px] font-mono font-black text-slate-600 uppercase tracking-tighter">{s} Index</span>
                  <span className={`text-sm font-mono font-black tracking-tighter ${s === 'NIFTY' ? 'text-cyan-400' : 'text-emerald-400'}`}>
                    {state?.prices?.[s]?.toLocaleString() || '---'}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Master Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">

            {/* Widget 1: Regime Sentinel */}
            <section className="tactical-panel bg-white/[0.02]">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-[10px] font-mono font-black text-slate-500 tracking-widest uppercase flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5" /> Market Regime
                </h3>
                <span className={`text-[10px] font-mono font-black px-2 py-0.5 border ${state?.regime === 'TRENDING' ? 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10' : 'border-amber-500/20 text-amber-500 bg-amber-500/10'}`}>
                  {state?.regime || 'UNCERTAIN'}
                </span>
              </div>
              <div className="space-y-4">
                <div className="p-3 bg-black/40 border border-white/[0.03] rounded-xs">
                  <p className="text-[10px] text-slate-500 font-mono leading-relaxed font-bold uppercase text-center italic tracking-widest">
                    {state?.market_message || 'SYSTEM_CALIBRATING'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-[10px] font-mono font-black text-slate-600">
                  <div className="flex flex-col">
                    <span className="opacity-50 tracking-tighter mb-1">ADVANCES</span>
                    <span className="text-emerald-400 text-sm tracking-tighter">
                      {state?.market_message === 'MARKET_CLOSED' ? '-' : (state?.breadth?.advances || '0')}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="opacity-50 tracking-tighter mb-1">DECLINES</span>
                    <span className="text-rose-400 text-sm tracking-tighter">
                      {state?.market_message === 'MARKET_CLOSED' ? '-' : (state?.breadth?.declines || '0')}
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* Widget 2: Institutional Flow */}
            <section className="tactical-panel">
              <h3 className="text-[10px] font-mono font-black text-slate-500 tracking-widest uppercase mb-6 flex items-center gap-2">
                <Binary className="w-3.5 h-3.5" /> Flow Guardrails
              </h3>
              <div className="space-y-4 font-mono">
                <div className="flex justify-between group">
                  <span className="text-[10px] text-slate-600 uppercase font-black tracking-tighter group-hover:text-slate-400 transition-colors">IV Skew Bias</span>
                  <span className={`text-xs font-black tracking-tighter ${(state?.iv_skew?.[activeAsset] ?? 0) > 1.3 ? 'text-rose-500' : 'text-cyan-400'}`}>
                    {state?.market_message === 'MARKET_CLOSED' || state?.iv_skew?.[activeAsset] === 0 ? '-' : state?.iv_skew?.[activeAsset]?.toFixed(2) || '1.00'}
                  </span>
                </div>
                <div className="flex justify-between group">
                  <span className="text-[10px] text-slate-600 uppercase font-black tracking-tighter group-hover:text-slate-400 transition-colors">Sector Synergy</span>
                  <span className={`text-xs font-black tracking-tighter ${(state?.sector_synergy ?? 0) > 1.0 ? 'text-emerald-500' : 'text-amber-500'}`}>
                    {state?.market_message === 'MARKET_CLOSED' ? '-' : ((state?.sector_synergy ?? 0) > 1.0 ? 'Matched' : 'Drift')}
                  </span>
                </div>
                <div className="flex justify-between group">
                  <span className="text-[10px] text-slate-600 uppercase font-black tracking-tighter group-hover:text-slate-400 transition-colors">Institutional Max Pain</span>
                  <span className="text-xs font-black tracking-tighter text-rose-500">
                    {state?.market_message === 'MARKET_CLOSED' ? '-' : (state?.max_pain?.[activeAsset] || '-')}
                  </span>
                </div>
                <div className="flex justify-between group">
                  <span className="text-[10px] text-slate-600 uppercase font-black tracking-tighter group-hover:text-slate-400 transition-colors">Gamma Exposure</span>
                  <span className={`text-xs font-black tracking-tighter ${(state?.gex_bias?.[activeAsset] ?? 0) > 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                    {state?.market_message === 'MARKET_CLOSED' ? '-' : ((state?.gex_bias?.[activeAsset] ?? 0) > 0 ? 'LONG_G' : (state?.gex_bias?.[activeAsset] ?? 0) < 0 ? 'SHORT_G' : 'NEUTRAL')}
                  </span>
                </div>
              </div>
            </section>

            {/* Widget 3: Strategic Scoreboard */}
            <section className="tactical-panel bg-white/[0.01]">
              <h3 className="text-[10px] font-mono font-black text-slate-500 tracking-widest uppercase mb-6 flex items-center gap-2">
                <Target className="w-3.5 h-3.5" /> Strategic Score
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-black/40 border border-white/[0.04]">
                  <div className="text-[8px] text-slate-700 font-black uppercase mb-2 tracking-[0.2em]">Win_Ratio</div>
                  <div className="text-xl font-mono font-black text-cyan-400 leading-none tracking-tighter">
                    {state?.market_message === 'MARKET_CLOSED' ? '-' : `${accuracy?.win_rate || '0.0'}%`}
                  </div>
                </div>
                <div className="p-4 bg-black/40 border border-white/[0.04]">
                  <div className="text-[8px] text-slate-700 font-black uppercase mb-2 tracking-[0.2em]">Edge_Exp</div>
                  <div className="text-xl font-mono font-black text-emerald-400 leading-none tracking-tighter">
                    {state?.market_message === 'MARKET_CLOSED' ? '-' : `+${accuracy?.expectancy || '0.0'}`}
                  </div>
                </div>
              </div>
              {/* FIX #8: Removed hardcoded audit verdict */}
            </section>

            {/* Widget 4: Memory & Stability */}
            <section className="tactical-panel">
              <h3 className="text-[10px] font-mono font-black text-slate-500 tracking-widest uppercase mb-6 flex items-center gap-2">
                <Lock className="w-3.5 h-3.5" /> Evolution Pulse
              </h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-[9px] font-mono font-bold mb-2">
                    <span className="text-slate-600 uppercase tracking-tighter">Feature Authority</span>
                    <span className="text-emerald-500 tracking-tighter">1.0000</span>
                  </div>
                  <div className="h-[2px] bg-white/5 overflow-hidden">
                    <div className="h-full bg-emerald-500 w-full shadow-[0_0_10px_rgba(16,185,129,0.3)]" />
                  </div>
                </div>
                <div className="flex justify-between text-[10px] font-mono font-black text-slate-600 uppercase pt-2">
                  <span className="opacity-50">Resets Remaining</span>
                  <span className="text-cyan-400">1 / 1</span>
                </div>
                <div className="text-[8px] text-slate-800 font-mono italic leading-relaxed uppercase pt-2 border-t border-white/[0.03]">
                  Autonomous DNA calibrations occur post-session. Integrity lock active.
                </div>
              </div>
            </section>

          </div>

          {/* Execution & Order Board */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

            {/* Left: Signals (Order Tickets) */}
            <div className="lg:col-span-8 space-y-6">
              <div className="flex items-center justify-between px-2">
                <h2 className="text-xs font-black uppercase tracking-[0.3em] flex items-center gap-3 text-slate-600">
                  <Crosshair className="w-4 h-4" /> Tactical Execution Board
                </h2>
              </div>

              {state?.active_signals && state.active_signals.length > 0 ? (
                state.active_signals.map((signal, i) => (
                  <div key={i} className="bg-black/40 border border-white/[0.06] p-6 lg:p-10 relative overflow-hidden group">
                    <div className="absolute top-0 left-0 w-1 h-full bg-cyan-500 shadow-[0_0_20px_rgba(34,211,238,0.3)]" />

                    <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-8 mb-10">
                      <div>
                        <div className="flex items-center gap-3 mb-2">
                          <span className={`text-[8px] font-mono font-black px-2 py-0.5 border ${signal.logic_version?.includes('SKIRMISHER') ? 'text-amber-500 border-amber-500/20' : 'text-cyan-400 border-cyan-400/20'}`}>
                            {signal.logic_version?.includes('SKIRMISHER') ? 'ACTIVITY_SCALP' : 'ULTRA_ALPHA'}
                          </span>
                          <span className="text-[9px] font-mono text-slate-600 font-bold uppercase tracking-widest">{signal.decision_id || 'ID_NIF_X'}</span>
                        </div>
                        <h3 className="text-4xl font-black italic data-text leading-none text-white uppercase">{signal.option_symbol || signal.symbol}</h3>
                        <p className="text-[10px] font-mono text-cyan-400/70 font-black mt-4 uppercase tracking-[0.2em]">{signal.reasoning}</p>
                      </div>

                      <div className="flex items-center gap-6">
                        <div className="text-right flex flex-col items-end">
                          <span className="text-[9px] font-mono text-slate-700 font-bold uppercase tracking-widest mb-1">Conf. Rating</span>
                          <span className="text-xl font-mono font-black text-slate-300 tracking-tighter">{(signal.confidence_val || 0.85).toFixed(2)}</span>
                        </div>
                        <button className="px-8 py-3 bg-white hover:bg-cyan-400 text-black font-black text-[10px] uppercase tracking-[0.4em] transition-all cursor-pointer">
                          EXECUTE
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-6 font-mono border-t border-white/[0.03] pt-8">
                      <div>
                        <span className="text-[9px] text-slate-700 font-black uppercase block mb-2 tracking-widest">Buy_Point</span>
                        <span className="text-2xl font-black text-emerald-400 tabular-nums tracking-tighter">₹{signal.premium_entry || signal.entry_price}</span>
                      </div>
                      <div>
                        <span className="text-[9px] text-slate-700 font-black uppercase block mb-2 tracking-widest">Risk_Floor</span>
                        <span className="text-2xl font-black text-rose-500 tabular-nums tracking-tighter">₹{signal.premium_sl || signal.stop_loss}</span>
                      </div>
                      <div>
                        <span className="text-[9px] text-slate-700 font-black uppercase block mb-2 tracking-widest">Alpha_Ceil</span>
                        <span className="text-2xl font-black text-cyan-400 tabular-nums tracking-tighter">₹{signal.premium_target || signal.target}</span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="border border-white/[0.02] bg-white/[0.005] py-24 md:py-32 flex flex-col items-center justify-center text-center px-10">
                  <Binary className="w-12 h-12 text-slate-800 mb-6 opacity-20" />
                  <h3 className="text-[10px] font-black text-slate-800 uppercase tracking-[0.6em] italic">Statistically Silent Zone</h3>
                  <p className="text-[10px] text-slate-900 font-mono mt-4 uppercase max-w-[320px] leading-relaxed tracking-[0.1em] font-black opacity-20">No institutional footprints identified. Standby for orthogonal convergence.</p>
                </div>
              )}
            </div>

            {/* Right: History & Logs */}
            <div className="lg:col-span-4 space-y-6">
              <section className="tactical-panel bg-white/[0.01] flex flex-col min-h-[400px]">
                <h2 className="text-[10px] font-mono font-black text-slate-500 tracking-widest uppercase mb-8 flex items-center justify-between">
                  <span className="flex items-center gap-2"><History className="w-3.5 h-3.5" /> Session Ledger</span>
                  <Shield className="w-3 h-3 opacity-20" />
                </h2>
                <div className="space-y-6 flex-grow overflow-y-auto max-h-[500px] pr-2 custom-scrollbar">
                  {history.length > 0 ? history.slice(0, 15).map((log, i) => (
                    <div key={i} className="flex justify-between items-center group border-b border-white/[0.02] pb-6 last:border-0">
                      <div>
                        <span className="text-xs font-black text-slate-300 uppercase tracking-tighter">{log.symbol}</span>
                        <div className="flex items-center gap-3 mt-1.5 opacity-50">
                          <span className="text-[8px] font-mono font-bold text-slate-600 uppercase">{new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          <span className="text-[8px] font-mono font-bold text-slate-700">|</span>
                          <span className={`text-[8px] font-mono font-black uppercase ${log.value === 'WIN' ? 'text-emerald-500' : 'text-rose-500'}`}>{log.value}</span>
                        </div>
                      </div>
                      <Eye className="w-3 h-3 text-slate-800 group-hover:text-cyan-400 transition-colors" />
                    </div>
                  )) : (
                    <div className="flex flex-col items-center justify-center py-20 opacity-10 grayscale">
                      <Binary className="w-10 h-10 mb-4 text-slate-700" />
                      <span className="text-[9px] font-mono uppercase tracking-widest font-black">Link Pending...</span>
                    </div>
                  )}
                </div>
              </section>

              {/* Widget: Stream of Consciousness (Epistemic Transparency) */}
              <section className="tactical-panel bg-black/40 border-cyan-500/10 h-[400px] flex flex-col">
                <div className="flex items-center justify-between mb-6">
                  <span className="label-text flex items-center gap-2">
                    <Binary className="w-3.5 h-3.5 text-cyan-500" /> Epistemic Flow
                  </span>
                  {state?.is_learning && (
                    <span className="text-[8px] font-mono text-emerald-400 animate-pulse uppercase font-black">DNA Calibration Active</span>
                  )}
                </div>

                <div className="flex-grow overflow-y-auto custom-scrollbar space-y-4 pr-2">
                  {state?.thought_logs && state.thought_logs.length > 0 ? (
                    state.thought_logs.slice().reverse().map((thought, i) => (
                      <div key={i} className="thought-entry group">
                        <div className="flex justify-between items-start mb-1">
                          <span className={`text-[8px] font-mono font-black border px-1.5 py-0.5 ${thought.type === 'VETO' ? 'border-rose-500/20 text-rose-500' :
                            thought.type === 'LEARN' ? 'border-emerald-500/20 text-emerald-400' :
                              'border-cyan-500/20 text-cyan-400'
                            }`}>
                            {thought.type}
                          </span>
                          <span className="text-[7px] font-mono text-slate-800 font-bold">
                            {new Date(thought.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </span>
                        </div>
                        <p className="text-[10px] font-mono text-slate-400 leading-relaxed group-hover:text-slate-200 transition-colors">
                          {thought.msg}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full opacity-20 grayscale">
                      <Cpu className="w-8 h-8 mb-4 text-slate-700" />
                      <span className="text-[9px] font-mono uppercase tracking-widest font-black">Awaiting Neural Activity...</span>
                    </div>
                  )}
                </div>
              </section>
            </div>

          </div>

          {/* Institutional Methodology (Muted Footer Sections) */}
          <footer className="mt-20 pt-16 border-t border-white/[0.03] space-y-20 pb-40">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-x-12 gap-y-16">
              {[
                { title: "Unified Sigma Gate", desc: "Price anchors are validated against a two-tier gate dispersion from a single unified epistemic history source." },
                { title: "ATM Liquidity Bias", desc: "Pick liquidity-dominant contracts (OI/Volume) over nearest-neighbor ATM to ensure execution quality." },
                { title: "Expiry Sensitivity", desc: "Conditioned on time-to-expiry to avoid Gamma distortions near the terminal session." },
                { title: "Advisory Autonomy", desc: "Self-calibrating feature weights within bounded reputation limits under strict governor control." }
              ].map((item, i) => (
                <div key={i}>
                  <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4 border-l border-cyan-500/30 pl-3">{item.title}</h4>
                  <p className="text-[10px] text-slate-700 uppercase leading-relaxed font-bold font-mono">{item.desc}</p>
                </div>
              ))}
            </div>

            <div className="flex flex-col md:flex-row justify-between items-center gap-10 opacity-30 group">
              <div className="flex items-center gap-12 text-[9px] font-mono font-black text-slate-700 uppercase tracking-[0.4em]">
                <span className="flex items-center gap-3"><Zap className="w-4 h-4 text-cyan-500/50" /> Statistical Agency</span>
                <span className="flex items-center gap-3"><Lock className="w-4 h-4 text-emerald-500/50" /> Integrity Lock</span>
              </div>
              <div className="flex flex-col items-center md:items-end gap-2">
                <div className="text-[9px] font-mono text-slate-800 font-black uppercase tracking-widest">
                  &copy; 2026 THE ORACLE // v9.4.0_PROD // AUTH_SYNC_COMPLETE
                </div>
                <div className="text-[7px] font-mono text-slate-900 font-black uppercase tracking-[0.5em] group-hover:text-slate-700 transition-colors">
                  Built for Institutional Preservation
                </div>
              </div>
            </div>
          </footer>

        </div>
      </div>

    </main>
  );
}
