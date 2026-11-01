"""Построение графиков на основе сохранённой истории цен."""

from __future__ import annotations

from plotly.graph_objects import Figure, Scatter


def build_price_chart(snapshots, title: str = "Динамика цены") -> str:
    points = list(snapshots)
    if not points:
        return (
            '<div class="alert alert-secondary">'
            "История цен пока не накоплена. Запустите обновление рыночных данных."
            "</div>"
        )
    figure = Figure(
        data=[
            Scatter(
                x=[point.captured_at for point in points],
                y=[float(point.price) for point in points],
                mode="lines",
                name="Цена",
                line={"color": "#0d6efd", "width": 2},
                hovertemplate="%{x|%d.%m.%Y %H:%M}<br>%{y:.2f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        height=420,
        template="plotly_white",
        xaxis_title="Дата",
        yaxis_title="Цена",
    )
    return figure.to_html(
        full_html=False,
        include_plotlyjs=False,
        include_mathjax=False,
        config={"displayModeBar": False, "responsive": True},
        div_id="price-chart",
    )
