from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from config.settings import logger
from strategy.forms import StrategyForm, StrategyRuleForm
from strategy.models import Strategy, StrategyRule, StrategyTrade
from strategy.services import run_strategy_now, strategy_metrics


def _owned_strategy(request, pk: int) -> Strategy:
    return get_object_or_404(Strategy, pk=pk, user=request.user)


class StrategyListView(LoginRequiredMixin, View):
    template_name = "strategy/index.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "strategies": Strategy.objects.filter(user=request.user).select_related(
                    "share"
                ),
                "form": StrategyForm(),
            },
        )

    def post(self, request):
        form = StrategyForm(request.POST)
        if form.is_valid():
            strategy = form.save(commit=False)
            strategy.user = request.user
            strategy.cash = strategy.initial_cash
            strategy.save()
            messages.success(request, "Стратегия создана")
            return redirect("strategy:detail", pk=strategy.pk)
        return render(
            request,
            self.template_name,
            {
                "strategies": Strategy.objects.filter(user=request.user).select_related(
                    "share"
                ),
                "form": form,
            },
        )


class StrategyDetailView(LoginRequiredMixin, View):
    template_name = "strategy/detail.html"

    def _context(self, strategy, rule_form=None):
        return {
            "strategy": strategy,
            "metrics": strategy_metrics(strategy),
            "rules": strategy.rules.all(),
            "trades": StrategyTrade.objects.filter(strategy=strategy).select_related(
                "rule"
            )[:100],
            "rule_form": rule_form or StrategyRuleForm(),
        }

    def get(self, request, pk):
        strategy = _owned_strategy(request, pk)
        return render(request, self.template_name, self._context(strategy))

    def post(self, request, pk):
        strategy = _owned_strategy(request, pk)
        form = StrategyRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.strategy = strategy
            rule.save()
            messages.success(request, "Правило добавлено")
            return redirect("strategy:detail", pk=strategy.pk)
        return render(
            request, self.template_name, self._context(strategy, rule_form=form)
        )


class StrategyToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        strategy = _owned_strategy(request, pk)
        strategy.is_active = not strategy.is_active
        strategy.save(update_fields=["is_active"])
        messages.info(
            request,
            "Стратегия включена" if strategy.is_active else "Стратегия выключена",
        )
        return redirect("strategy:detail", pk=strategy.pk)


class StrategyRuleToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        rule = get_object_or_404(StrategyRule, pk=pk, strategy__user=request.user)
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active"])
        return redirect("strategy:detail", pk=rule.strategy_id)


class StrategyRuleDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        rule = get_object_or_404(StrategyRule, pk=pk, strategy__user=request.user)
        strategy_pk = rule.strategy_id
        try:
            rule.delete()
            messages.success(request, "Правило удалено")
        except ProtectedError:
            messages.error(
                request,
                "По правилу уже есть сделки — его нельзя удалить, только выключить",
            )
        return redirect("strategy:detail", pk=strategy_pk)


class StrategyRunView(LoginRequiredMixin, View):
    def post(self, request, pk):
        strategy = _owned_strategy(request, pk)
        try:
            trades = run_strategy_now(strategy)
        except Exception as exc:  # noqa: BLE001 - ошибка провайдера не должна давать 500
            logger.error("Не удалось проверить стратегию %s: %s", strategy.pk, exc)
            messages.error(
                request,
                "Не удалось получить рыночную цену. Проверьте настройки провайдера.",
            )
            return redirect("strategy:detail", pk=strategy.pk)
        if trades:
            messages.success(request, f"Выполнено сделок: {len(trades)}")
        else:
            messages.info(request, "Условия не выполнены, новых сделок нет")
        return redirect("strategy:detail", pk=strategy.pk)


class StrategyDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        strategy = _owned_strategy(request, pk)
        strategy.delete()
        messages.success(request, "Стратегия удалена")
        return redirect("strategy:index")
