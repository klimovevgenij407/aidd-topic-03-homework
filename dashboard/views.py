"""HTML views for the share catalogue."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from dashboard.forms import ShareForm
from dashboard.models import Share
from dashboard.services.market_data import MarketDataError
from dashboard.services.price_history import get_history

logger = logging.getLogger(__name__)

PERIOD_CHOICES = (
    (7, "7 дней"),
    (30, "30 дней"),
    (90, "90 дней"),
    (180, "180 дней"),
    (365, "1 год"),
)
PERIOD_VALUES = {value for value, _label in PERIOD_CHOICES}


def parse_period(raw_value: str | None) -> int:
    try:
        value = int(raw_value or 180)
    except (TypeError, ValueError):
        return 180
    return value if value in PERIOD_VALUES else 180


class ShareListView(ListView):
    """Публичный список акций."""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(DetailView):
    """Публичная карточка акции с графиком за выбранный период."""

    model = Share
    template_name = "dashboard/detail.html"
    context_object_name = "share"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = parse_period(self.request.GET.get("period"))
        context["period"] = period
        context["periods"] = PERIOD_CHOICES
        context["plot_div"] = ""
        context["chart_error"] = ""
        context["stats"] = None
        context["snapshots"] = []

        try:
            snapshots, stats, plot_div = get_history(self.object, days=period)
            context["snapshots"] = snapshots
            context["stats"] = stats
            context["plot_div"] = plot_div
        except MarketDataError as exc:
            logger.warning("Chart unavailable for share %s: %s", self.object.pk, exc)
            context["chart_error"] = (
                "График временно недоступен: не удалось получить рыночные данные."
            )
            messages.warning(self.request, context["chart_error"])

        if not context["plot_div"] and not context["chart_error"]:
            context["chart_error"] = "За выбранный период исторических данных нет."
        return context


class ShareCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Добавление акции."""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareForm
    success_url = reverse_lazy("dashboard:index")
    success_message = "Акция «%(name)s» добавлена."


class ShareUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Редактирование акции."""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareForm
    success_url = reverse_lazy("dashboard:index")
    success_message = "Акция «%(name)s» сохранена."


class ShareDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление акции."""

    model = Share
    template_name = "dashboard/delete.html"
    context_object_name = "share"
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        messages.success(self.request, f"Акция «{self.object.name}» удалена.")
        return super().form_valid(form)
