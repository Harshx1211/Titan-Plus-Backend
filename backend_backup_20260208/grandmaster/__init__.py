"""
Titan Plus: Grandmaster Engine
Institutional-grade trading logic modules for advanced market analysis.

Modules:
    - smc: Smart Money Concepts analyzer (BOS, ChoCh, Order Blocks, FVG)
    - greeks: Options flow analyzer (GEX, Gamma Exposure, Dealer positioning)
    - macro: Macro regime analyzer (VIX, DXY, FII flows)
    - nuclear: Master scorecard for trade decision making
"""

from .smc import SMCAnalyzer
from .greeks import GammaEngine
from .macro import MacroRegime
from .nuclear import NuclearScorecard

__version__ = "1.0.0"
__all__ = ["SMCAnalyzer", "GammaEngine", "MacroRegime", "NuclearScorecard"]
