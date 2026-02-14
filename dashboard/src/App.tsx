import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { MarketStats } from './components/MarketStats';
import { NeuralFeed } from './components/NeuralFeed';
import { ActiveSignal } from './components/ActiveSignal';
import { MetricCards } from './components/MetricCards';
import { InstitutionalFeed } from './components/InstitutionalFeed';
import { ActiveTrade, MarketStat, HistoricSignal } from './types';

export default function App() {
    const [activeTrade, setActiveTrade] = useState<ActiveTrade | null>(null);
    const [historicSignals, setHistoricSignals] = useState<HistoricSignal[]>([]);
    const [wsStatus, setWsStatus] = useState<'connecting' | 'online' | 'offline'>('connecting');
    const [thoughts, setThoughts] = useState<string[]>([]);
    const [marketStats, setMarketStats] = useState<MarketStat[]>([
        { symbol: 'BTC/INR', price: 4425000, change: 2.4, volume: '2.1B' },
        { symbol: 'ETH/INR', price: 215000, change: -1.2, volume: '840M' },
        { symbol: 'SOL/INR', price: 9200, change: 5.7, volume: '420M' },
        { symbol: 'DOGE/INR', price: 14.2, change: 0.8, volume: '110M' },
    ]);

    const thoughtEndRef = useRef<HTMLDivElement>(null);

    // Smart Backend Detection
    const getBackendConfig = () => {
        let wsUrl = import.meta.env.VITE_WS_URL;
        let apiUrl = import.meta.env.VITE_API_URL;

        if (!wsUrl || !apiUrl) {
            const isVercel = window.location.hostname.includes('vercel.app');
            // Fallback for Vercel to connect to the Hugging Face backend
            const hfHost = 'harshx1323-trading-bot.hf.space';

            const targetHost = isVercel ? hfHost : window.location.host;
            const wsProtocol = window.location.protocol === 'https:' || isVercel ? 'wss:' : 'ws:';
            const httpProtocol = window.location.protocol === 'https:' || isVercel ? 'https:' : 'http:';

            wsUrl = wsUrl || `${wsProtocol}//${targetHost}/ws/market`;
            apiUrl = apiUrl || `${httpProtocol}//${targetHost}`;
        }
        return { wsUrl, apiUrl };
    };

    const { wsUrl, apiUrl } = getBackendConfig();

    useEffect(() => {
        thoughtEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [thoughts]);

    useEffect(() => {
        // 1. Initial Data Fetching
        const fetchInitialData = async () => {
            try {
                const [sigRes, thoughtRes] = await Promise.all([
                    fetch(`${apiUrl}/api/signals`),
                    fetch(`${apiUrl}/api/thoughts`)
                ]);

                if (sigRes.ok) {
                    const data = await sigRes.json();
                    const signalsArray = Array.isArray(data) ? data : (data.value || []);
                    setHistoricSignals(signalsArray);
                }

                if (thoughtRes.ok) {
                    const data = await thoughtRes.json();
                    const thoughtsArray = Array.isArray(data) ? data : (data.value || []);
                    const formatted = thoughtsArray.map((t: any) =>
                        `[${new Date(t.created_at).toLocaleTimeString()}] ${t.sentiment}: ${t.symbol} - ${t.market_regime}`
                    ).reverse();
                    setThoughts(formatted);
                }
            } catch (err) {
                console.error("Failed to fetch initial data:", err);
            }
        };

        fetchInitialData();

        // 2. WebSocket Connection
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setWsStatus('online');
            addThought('Neural link established. Titan V3.1 Online.');
        };

        ws.onclose = () => {
            setWsStatus('offline');
            addThought('Neural link severed. Offline mode engaged.');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'update') {
                if (data.active_trade) {
                    // Map backend data to frontend format
                    const rawTargets = data.active_trade.targets || {};
                    const targetList = Object.entries(rawTargets).map(([key, val]: [string, any]) => ({
                        price: typeof val === 'number' ? val : (val.price || 0),
                        hit: typeof val === 'number' ? false : (val.hit || false)
                    }));

                    setActiveTrade({
                        symbol: data.active_trade.symbol,
                        side: data.active_trade.side,
                        entry_price: data.active_trade.entry_price,
                        stop_loss: data.active_trade.stop_loss || 0,
                        targets: targetList.length > 0 ? targetList : [{ price: 0, hit: false }],
                        confidence: data.active_trade.confidence || data.active_trade.metadata?.confidence || 0.85,
                        pnl_inr: (data.active_trade.unrealized_pnl || data.active_trade.pnl || 0) * 83.0
                    });
                } else {
                    setActiveTrade(null);
                }
            }
        };

        // 3. Heartbeat to keep connection alive
        const heartbeat = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 20000);

        return () => {
            clearInterval(heartbeat);
            ws.close();
        };
    }, [wsUrl, apiUrl]);

    const addThought = (msg: string) => {
        setThoughts((prev: string[]) => [...prev.slice(-15), `[${new Date().toLocaleTimeString()}] ${msg}`]);
    };

    return (
        <div className="min-h-screen bg-[#05060a] text-[#e2e8f0] font-sans relative overflow-hidden">
            {/* Background Effects */}
            <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-sky-500/10 rounded-full blur-[120px]" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 rounded-full blur-[120px]" />
                <div className="scanline" />
            </div>

            <div className="max-w-[1600px] mx-auto p-4 md:p-8 relative z-10">
                <Header wsStatus={wsStatus} />

                <div className="grid grid-cols-12 gap-6">
                    {/* LEFT COLUMN */}
                    <div className="col-span-12 lg:col-span-3 space-y-6">
                        <MarketStats stats={marketStats} />
                        <NeuralFeed thoughts={thoughts} thoughtEndRef={thoughtEndRef} />
                    </div>

                    {/* CENTER COLUMN */}
                    <div className="col-span-12 lg:col-span-6 space-y-6">
                        <ActiveSignal activeTrade={activeTrade} />
                        <MetricCards />
                    </div>

                    {/* RIGHT COLUMN */}
                    <div className="col-span-12 lg:col-span-3 space-y-6">
                        <InstitutionalFeed signals={historicSignals} />
                    </div>
                </div>

                {/* FOOTER */}
                <footer className="mt-12 pt-8 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-6">
                    <div className="flex items-center gap-8">
                        <div className="flex flex-col">
                            <span className="text-[9px] text-slate-500 font-black uppercase tracking-widest mb-1">DB Connection</span>
                            <span className="text-[10px] text-emerald-500 font-black uppercase">Supabase Active</span>
                        </div>
                        <div className="flex flex-col">
                            <span className="text-[9px] text-slate-500 font-black uppercase tracking-widest mb-1">Currency Mode</span>
                            <span className="text-[10px] text-sky-400 font-black uppercase tracking-tight">Rupees (₹)</span>
                        </div>
                    </div>
                    <p className="text-[10px] text-slate-600 font-medium">© 2026 Titan Brain Institutional. Secure Trading Interface.</p>
                </footer>
            </div>
        </div>
    );
}
