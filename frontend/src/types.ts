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
