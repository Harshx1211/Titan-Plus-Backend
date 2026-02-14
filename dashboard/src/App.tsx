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

export default function App() {
    const [activeTrade, setActiveTrade] = useState<ActiveTrade | null>(null);
    const [historicSignals, setHistoricSignals] = useState<HistoricSignal[]>([]);
    const [wsStatus, setWsStatus] = useState<'connecting' | 'online' | 'offline'>('connecting');
    const [thoughts, setThoughts] = useState<string[]>([]);
    const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
        winRate: 0,
        totalSignals: 0,
        avgRMultiple: 0,
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

    // Smart Backend Detection
    const getBackendConfig = () => {
        const hostname = window.location.hostname;
        const isVercel = hostname.includes('vercel.app');

        // 1. Force HF Backend if on Vercel
        if (isVercel) {
            const targetHF = "harshx1211-titan-plus-backend.hf.space";
            return {
                wsUrl: `wss://${targetHF}/ws/market`,
                apiUrl: `https://${targetHF}`
            };
        }

        // 2. Localhost or HF Space direct
        const host = window.location.host;
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const httpProtocol = window.location.protocol === 'https:' ? 'https:' : 'http:';

        const isHF = hostname.includes('hf.space');
        if (isHF) {
            return {
                wsUrl: `${wsProtocol}//${host}/ws/market`,
                apiUrl: `${httpProtocol}//${host}`
            };
        }

        // 3. Fallback/Local
        const isProduction = hostname !== 'localhost' && hostname !== '127.0.0.1';
        const targetHost = isProduction ? host : 'localhost:8000';
        return {
            wsUrl: `${wsProtocol}//${targetHost}/ws/market`,
            apiUrl: `${httpProtocol}//${targetHost}`
        };
    };

    const { wsUrl, apiUrl } = getBackendConfig();

    useEffect(() => {
        thoughtEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [thoughts]);

    useEffect(() => {
        // Initial Data Fetching
        const fetchInitialData = async () => {
            try {
                const [sigRes, thoughtRes, metricsRes] = await Promise.all([
                    fetch(`${apiUrl}/api/signals`).catch(() => null),
                    fetch(`${apiUrl}/api/thoughts`).catch(() => null),
                    fetch(`${apiUrl}/api/metrics`).catch(() => null)
                ]);

                if (sigRes?.ok) {
                    const data = await sigRes.json();
                    const signalsArray = Array.isArray(data) ? data : (data.value || []);
                    setHistoricSignals(signalsArray.slice(0, 10));
                }

                if (thoughtRes?.ok) {
                    const data = await thoughtRes.json();
                    const thoughtsArray = Array.isArray(data) ? data : (data.value || []);
                    const formatted = thoughtsArray
                        .map((t: any) => `${t.sentiment}: ${t.symbol} | ${t.market_regime}`)
                        .reverse()
                        .slice(0, 20);
                    setThoughts(formatted);
                }

                if (metricsRes?.ok) {
                    const data = await metricsRes.json();
                    setSystemMetrics(prev => ({ ...prev, ...data }));
                }
            } catch (err) {
                console.error("Failed to fetch initial data:", err);
            }
        };

        fetchInitialData();

        // WebSocket Connection
        let ws: WebSocket | null = null;
        let reconnectTimeout: any;

        const connectWebSocket = () => {
            try {
                addThought(`📡 Linking to: ${wsUrl}...`);
                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    setWsStatus('online');
                    addThought('🟢 Neural link established');
                };

                ws.onclose = () => {
                    setWsStatus('offline');
                    addThought('🔴 Connection lost. Reconnecting...');
                    reconnectTimeout = setTimeout(connectWebSocket, 5000);
                };

                ws.onerror = () => {
                    setWsStatus('offline');
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === 'update') {
                            if (data.active_trade) {
                                const rawTargets = data.active_trade.targets || {};
                                const targetList = Object.entries(rawTargets).map(([key, val]: [string, any]) => ({
                                    price: typeof val === 'number' ? val : (val.price || 0),
                                    hit: typeof val === 'number' ? false : (val.hit || false),
                                    label: key.toUpperCase()
                                }));

                                setActiveTrade({
                                    symbol: data.active_trade.symbol,
                                    side: data.active_trade.side,
                                    entry_price: data.active_trade.entry_price,
                                    stop_loss: data.active_trade.stop_loss || 0,
                                    targets: targetList.length > 0 ? targetList : [{ price: 0, hit: false, label: 'TP1' }],
                                    confidence: data.active_trade.confidence || data.active_trade.metadata?.confidence || 0.85,
                                    pnl_inr: (data.active_trade.unrealized_pnl || data.active_trade.pnl || 0) * 83.0,
                                    rr_ratio: data.active_trade.rr_ratio || 2.5,
                                    duration: data.active_trade.duration || 0
                                });
                            } else {
                                setActiveTrade(null);
                            }

                            if (data.metrics) {
                                setSystemMetrics(prev => ({ ...prev, ...data.metrics }));
                            }

                            if (data.thought) {
                                addThought(data.thought);
                            }

                            if (data.market_data) {
                                // Update market stats from live feed if available
                                setMarketStats(prev => prev.map(stat => {
                                    const update = data.market_data[stat.symbol];
                                    if (update) {
                                        return {
                                            ...stat,
                                            price: update.price,
                                            change: update.change_24h || stat.change,
                                            volume: update.volume || stat.volume,
                                            high24h: update.high_24h || stat.high24h,
                                            low24h: update.low_24h || stat.low24h
                                        };
                                    }
                                    return stat;
                                }));
                            }
                        }
                    } catch (err) {
                        console.error('WebSocket message error:', err);
                    }
                };
            } catch (err) {
                console.error('WebSocket connection error:', err);
                setWsStatus('offline');
            }
        };

        connectWebSocket();

        // Heartbeat
        const heartbeat = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 20000);

        return () => {
            clearInterval(heartbeat);
            clearTimeout(reconnectTimeout);
            ws?.close();
        };
    }, [wsUrl, apiUrl]);

    const addThought = (msg: string) => {
        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        setThoughts((prev) => {
            const next = [...prev, `[${timestamp}] ${msg}`];
            return next.slice(-20);
        });
    };

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
