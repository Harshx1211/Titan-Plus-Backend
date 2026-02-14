import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Header } from './components/Header';
import { MarketOverview } from './components/MarketOverview';
import { ActivePosition } from './components/ActivePosition';
import { PerformanceMetrics } from './components/PerformanceMetrics';
import { BrainActivity } from './components/BrainActivity';
import { SignalHistory } from './components/SignalHistory';
import { SystemStatus } from './components/SystemStatus';
import { ActiveTrade, MarketStat, HistoricSignal, SystemMetrics } from './types';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = "https://eiafuzgqbtfstaparhpe.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVpYWZ1emdxYnRmc3RhcGFyaHBlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkzNDQ3MjksImV4cCI6MjA4NDkyMDcyOX0.YUDSTdL6O3HGKLFqUdaDg1DMnogLvAzZY5nh7xh9Y1Y";
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export default function App() {
    const [activeTrade, setActiveTrade] = useState<ActiveTrade | null>(null);
    const [historicSignals, setHistoricSignals] = useState<HistoricSignal[]>([]);
    const [wsStatus, setWsStatus] = useState<'connecting' | 'online' | 'offline'>('connecting');
    const [thoughts, setThoughts] = useState<string[]>([]);
    const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
        winRate: 0,
        totalSignals: 142,
        avgRMultiple: 2.1,
        profitFactor: 0,
        aiConfidence: 85,
        activeFilters: 3
    });

    const [marketStats, setMarketStats] = useState<MarketStat[]>([
        { symbol: 'BTC/USDT', price: 0, change: 0, volume: '...', high24h: 0, low24h: 0 },
        { symbol: 'ETH/USDT', price: 0, change: 0, volume: '...', high24h: 0, low24h: 0 },
        { symbol: 'SOL/USDT', price: 0, change: 0, volume: '...', high24h: 0, low24h: 0 },
    ]);

    const thoughtEndRef = useRef<HTMLDivElement>(null);

    const addThought = (msg: string) => {
        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        const formatted = `[${timestamp}] ${msg}`;
        setThoughts((prev) => {
            if (prev.length > 0 && prev[prev.length - 1].split('] ')[1] === msg) return prev;
            return [...prev, formatted].slice(-20);
        });
    };

    // Unified function to calculate PnL based on live stats
    const calculateLivePnL = (trade: ActiveTrade | null, stats: MarketStat[]) => {
        if (!trade) return 0;
        const currentStat = stats.find(s => s.symbol === trade.symbol);
        if (!currentStat || currentStat.price === 0) return 0;

        const priceDiff = currentStat.price - trade.entry_price;
        const pnlUsd = trade.side === 'LONG' ? priceDiff : -priceDiff;
        return pnlUsd * 83.0; // Return INR
    };

    useEffect(() => {
        const setupSupabase = async () => {
            setWsStatus('connecting');
            addThought('📡 Connecting to Supabase Data Bridge...');

            // 1. Initial Data Fetch
            // Filter: Only show "Active" trades that are less than 48 hours old to prevent stale test data
            const twoDaysAgo = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();

            const { data: initialTrade } = await supabase
                .from('trades')
                .select('*')
                .eq('status', 'OPEN')
                .gt('created_at', twoDaysAgo)
                .order('created_at', { ascending: false })
                .limit(1);

            if (initialTrade && initialTrade[0]) {
                const tr = initialTrade[0];
                setActiveTrade({
                    symbol: tr.symbol,
                    side: tr.side,
                    entry_price: tr.entry_price,
                    stop_loss: tr.stop_loss || 0,
                    targets: Object.entries(tr.targets || {}).map(([key, val]: any) => ({
                        price: typeof val === 'number' ? val : (val.price || 0),
                        hit: typeof val === 'number' ? false : (val.hit || false),
                        label: key.toUpperCase()
                    })),
                    confidence: tr.confidence || 0.85,
                    pnl_inr: 0, // Will be calculated by stats listener
                    rr_ratio: 2.5,
                    duration: (Date.now() - new Date(tr.created_at).getTime()) / (60000)
                });
            }

            const { data: initialThoughts } = await supabase.from('brain_logs').select('*').order('created_at', { ascending: false }).limit(10);
            if (initialThoughts) {
                setThoughts(initialThoughts.reverse().map(t => {
                    const time = new Date(t.created_at).toLocaleTimeString([], { hour12: false });
                    return `[${time}] ${t.sentiment}: ${t.symbol} | ${t.market_regime}`;
                }));
            }

            // 2. Realtime Subscriptions (Replacement for WebSocket)
            const channel = supabase.channel('titan-updates')
                .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'brain_logs' }, (payload: any) => {
                    const t = payload.new;
                    if (t && t.sentiment) {
                        addThought(`${t.sentiment}: ${t.symbol} | ${t.market_regime}`);
                    }
                })
                .on('postgres_changes', { event: '*', schema: 'public', table: 'trades' }, (payload: any) => {
                    const tr = payload.new;
                    if (!tr || !tr.status) return;

                    if (tr.status === 'OPEN') {
                        setActiveTrade({
                            symbol: tr.symbol,
                            side: tr.side,
                            entry_price: tr.entry_price,
                            stop_loss: tr.stop_loss || 0,
                            targets: Object.entries(tr.targets || {}).map(([key, val]: any) => ({
                                price: typeof val === 'number' ? val : (val.price || 0),
                                hit: typeof val === 'number' ? false : (val.hit || false),
                                label: key.toUpperCase()
                            })),
                            confidence: tr.confidence || 0.85,
                            pnl_inr: 0,
                            rr_ratio: 2.5,
                            duration: 0
                        });
                    } else if (tr.status === 'CLOSED') {
                        setActiveTrade(current => (current?.symbol === tr.symbol) ? null : current);
                        addThought(`✅ Trade Closed: ${tr.symbol} | P&L: ₹${((tr.pnl || 0) * 83.0).toFixed(2)}`);
                    }
                })
                .on('postgres_changes', { event: '*', schema: 'public', table: 'market_state' }, (payload: any) => {
                    const m = payload.new;
                    if (!m || !m.symbol) return;

                    setMarketStats(prev => {
                        const newStats = prev.map(s => s.symbol === m.symbol ? {
                            ...s,
                            price: m.price || s.price,
                            volume: m.volume?.toString() || s.volume
                        } : s);

                        // DYNAMIC PNL CALCULATION
                        setActiveTrade(current => {
                            if (!current || current.symbol !== m.symbol) return current;
                            return {
                                ...current,
                                pnl_inr: calculateLivePnL(current, newStats)
                            };
                        });

                        return newStats;
                    });
                })
                .subscribe((status) => {
                    if (status === 'SUBSCRIBED') {
                        setWsStatus('online');
                        addThought('✅ Supabase Bridge Linked');
                    } else if (status === 'CLOSED' || status === 'CHANNEL_ERROR') {
                        setWsStatus('offline');
                        addThought('⚠️ Bridge Link Discarded');
                    }
                });

            return channel;
        };

        const channelPromise = setupSupabase();

        return () => {
            channelPromise.then(c => c && supabase.removeChannel(c));
        };
    }, []);

    const apiUrl = "https://harshx1211-titan-plus-backend.hf.space";

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans relative overflow-hidden">
            {/* Animated Background */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-0 -left-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob" />
                <div className="absolute top-0 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-2000" />
                <div className="absolute -bottom-40 left-20 w-80 h-80 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-4000" />

                {/* Grid Pattern */}
                <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:50px_50px]" />

                {/* Scanline Effect */}
                <div className="scanline" />
            </div>

            <div className="relative z-10 max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
                <Header wsStatus={wsStatus} metrics={systemMetrics} />

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
                    {/* LEFT COLUMN - Market & System */}
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.5 }}
                        className="lg:col-span-3 space-y-6"
                    >
                        <MarketOverview stats={marketStats} />
                        <SystemStatus
                            wsStatus={wsStatus}
                            aiVersion="3.1.0-Evolution-Fixed"
                            uptime="24h 13m"
                            endpoint={apiUrl}
                        />
                        <BrainActivity thoughts={thoughts} thoughtEndRef={thoughtEndRef} />
                    </motion.div>

                    {/* CENTER COLUMN - Main Trading View */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="lg:col-span-6 space-y-6"
                    >
                        <ActivePosition activeTrade={activeTrade} />
                        <PerformanceMetrics metrics={systemMetrics} />
                    </motion.div>

                    {/* RIGHT COLUMN - History & Analytics */}
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="lg:col-span-3 space-y-6"
                    >
                        <SignalHistory signals={historicSignals} />
                    </motion.div>
                </div>

                {/* FOOTER */}
                <footer className="mt-12 pt-6 border-t border-white/5">
                    <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
                        <div className="flex items-center gap-6">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                <span>Supabase Active</span>
                            </div>
                            <div className="text-slate-700">|</div>
                            <div>
                                Mode: <span className="text-purple-400">Institutional Advisory</span>
                            </div>
                        </div>
                        <p className="text-slate-600 italic">
                            © 2026 Titan Brain V3.1 Apex • DeepMind Powered
                        </p>
                    </div>
                </footer>
            </div>
        </div>
    );
}
