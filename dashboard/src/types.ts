export interface ActiveTrade {
    symbol: string;
    side: 'LONG' | 'SHORT';
    entry_price: number;
    stop_loss: number;
    targets: { price: number; hit: boolean }[];
    confidence: number;
    pnl_inr?: number;
}

export interface MarketStat {
    symbol: string;
    price: number;
    change: number;
    volume: string;
}

export interface HistoricSignal {
    id: string;
    symbol: string;
    side: 'LONG' | 'SHORT';
    entry_price: number;
    pnl?: number;
    status: 'OPEN' | 'CLOSED';
    created_at: string;
}

export interface BrainThought {
    id: number;
    symbol: string;
    sentiment: string;
    logic_details: any;
    created_at: string;
}
