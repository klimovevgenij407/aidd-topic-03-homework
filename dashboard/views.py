from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from dashboard.forms import ShareModelForm
from dashboard.models import Share
from market.charts import build_price_chart
from market.models import PriceSnapshot
from market.services import ensure_history, history_stats

ALLOWED_HISTORY_PERIODS = (30, 90, 180, 365)


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    """Карточка акции с сохранённой историей цен."""

    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, pk=pk)
        try:
            days = int(request.GET.get("days", 180))
        except (TypeError, ValueError):
            days = 180
        days = days if days in ALLOWED_HISTORY_PERIODS else 180

        ensure_history(share, days=days)
        start = timezone.localdate() - timedelta(days=days)
        snapshots = list(
            PriceSnapshot.objects.filter(
                share=share, captured_at__date__gte=start
            ).order_by("captured_at")
        )
        stats = history_stats(snapshots)
        chart = build_price_chart(
            snapshots, title=f"{share.ticker}: динамика за {days} дней"
        )
        recent_snapshots = list(reversed(snapshots[-30:]))

        return render(
            request,
            "dashboard/detail.html",
            {
                "share": share,
                "plot_div": chart,
                "stats": stats,
                "days": days,
                "periods": ALLOWED_HISTORY_PERIODS,
                "recent_snapshots": recent_snapshots,
            },
        )


class ShareCreateView(LoginRequiredMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление инструмента"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")
