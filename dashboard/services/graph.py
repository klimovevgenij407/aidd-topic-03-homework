"""Backward-compatible chart service imports.

The implementation moved to :mod:`dashboard.services.price_history` when price
history storage was introduced.
"""

from dashboard.services.price_history import build_chart, get_graph

__all__ = ["build_chart", "get_graph"]
