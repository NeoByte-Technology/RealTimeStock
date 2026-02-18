"""
West Africa Financial Intelligence Agent - Core Module

Modular AI agent for financial analysis focused on West African stock markets (BRVM).
Use lazy imports to avoid loading heavy deps when not needed.
"""

def __getattr__(name):
    if name == "FinancialAgent":
        from core.agent import FinancialAgent
        return FinancialAgent
    if name == "AgentTools":
        from core.tools import AgentTools
        return AgentTools
    if name == "analyze_stock":
        from core.analyzer import analyze_stock
        return analyze_stock
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["FinancialAgent", "AgentTools", "analyze_stock"]
