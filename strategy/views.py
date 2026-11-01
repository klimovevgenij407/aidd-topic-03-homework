"""Views for the strategy simulator."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from strategy.forms import StrategyForm
from strategy.models import Strategy
from strategy.services import calculate_state, toggle_strategy


class UserStrategyMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class StrategyListView(LoginRequiredMixin, ListView):
    model = Strategy
    template_name = "strategy/strategy_list.html"
    context_object_name = "strategies"
    paginate_by = 20

    def get_queryset(self):
        return Strategy.objects.filter(user=self.request.user).select_related("share")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rows"] = [
            (strategy, calculate_state(strategy)) for strategy in context["strategies"]
        ]
        return context


class StrategyDetailView(UserStrategyMixin, DetailView):
    model = Strategy
    template_name = "strategy/strategy_detail.html"
    context_object_name = "strategy"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["state"] = calculate_state(self.object)
        context["trades"] = self.object.trades.select_related("price_snapshot").all()
        return context


class StrategyCreateView(LoginRequiredMixin, CreateView):
    model = Strategy
    form_class = StrategyForm
    template_name = "strategy/strategy_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Стратегия создана.")
        return super().form_valid(form)


class StrategyUpdateView(UserStrategyMixin, UpdateView):
    model = Strategy
    form_class = StrategyForm
    template_name = "strategy/strategy_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Стратегия сохранена.")
        return super().form_valid(form)


class StrategyDeleteView(UserStrategyMixin, DeleteView):
    model = Strategy
    template_name = "strategy/strategy_confirm_delete.html"
    context_object_name = "strategy"
    success_url = reverse_lazy("strategy:strategy_list")

    def form_valid(self, form):
        messages.success(self.request, "Стратегия удалена.")
        return super().form_valid(form)


class StrategyToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        strategy = get_object_or_404(Strategy, pk=pk, user=request.user)
        toggle_strategy(strategy)
        state = "включена" if strategy.is_active else "выключена"
        messages.success(request, f"Стратегия {state}.")
        return redirect("strategy:strategy_detail", pk=strategy.pk)
