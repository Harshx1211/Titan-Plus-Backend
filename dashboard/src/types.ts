export interface ActiveTrade {
    symbol: string;
    side: 'LONG' | 'SHORT';
    entry_price: number;
    stop_loss: number;
    targets: { price: number; hit: boolean; label: string }[];
    confidence: number;
    pnl_inr?: number;
    rr_ratio?: number;
    duration?: number;
}

export interface MarketStat {
    symbol: string;
    price: number;
    change: number;
    volume: string;
    high24h: number;
    low24h: number;
}

export interface HistoricSignal {
    id: string;
    symbol: string;
    side: 'LONG' | 'SHORT';
    entry_price: number;
    exit_price?: number;
    pnl?: number;
    status: 'OPEN' | 'CLOSED';
    created_at: string;
    entry_reason?: string;
    r_multiple?: number;
}

export interface BrainThought {
    id: number;
    symbol: string;
    sentiment: string;
    logic_details: any;
    market_regime: string;
    created_at: string;
}

export interface SystemMetrics {
    winRate: number;
    totalSignals: number;
    avgRMultiple: number;
    profitFactor: number;
    aiConfidence: number;
    activeFilters: number;
    recentWinRate?: number;
    totalPnl?: number;
}

export interface SystemMetrics {
    winRate: number;
    totalSignals: number;
    avgRMultiple: number;
    profitFactor: number;
    aiConfidence: number;
    activeFilters: number;
    recentWinRate?: number;
    totalPnl?: number;
}
