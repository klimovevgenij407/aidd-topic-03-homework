from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from portfolio.forms import PortfolioForm, TradeForm
from portfolio.models import Portfolio, Transaction
from portfolio.services import TradeError, execute_trade, portfolio_valuation


def _owned_portfolio(request, pk: int) -> Portfolio:
    return get_object_or_404(Portfolio, pk=pk, user=request.user)


class PortfolioListView(LoginRequiredMixin, View):
    template_name = "portfolio/index.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "portfolios": Portfolio.objects.filter(user=request.user),
                "form": PortfolioForm(),
            },
        )

    def post(self, request):
        form = PortfolioForm(request.POST)
        if form.is_valid():
            portfolio = form.save(commit=False)
            portfolio.user = request.user
            portfolio.cash = portfolio.initial_cash
            portfolio.save()
            messages.success(request, "Портфель создан")
            return redirect("portfolio:detail", pk=portfolio.pk)
        return render(
            request,
            self.template_name,
            {"portfolios": Portfolio.objects.filter(user=request.user), "form": form},
        )


class PortfolioDetailView(LoginRequiredMixin, View):
    template_name = "portfolio/detail.html"

    def get(self, request, pk):
        portfolio = _owned_portfolio(request, pk)
        return render(
            request,
            self.template_name,
            {
                "portfolio": portfolio,
                "valuation": portfolio_valuation(portfolio),
                "transactions": Transaction.objects.filter(portfolio=portfolio)
                .select_related("share")[:100],
                "trade_form": TradeForm(),
            },
        )

    def post(self, request, pk):
        portfolio = _owned_portfolio(request, pk)
        form = TradeForm(request.POST)
        if form.is_valid():
            try:
                execute_trade(
                    portfolio=portfolio,
                    share=form.cleaned_data["share"],
                    side=form.cleaned_data["side"],
                    quantity=form.cleaned_data["quantity"],
                    price=form.cleaned_data["price"],
                    note=form.cleaned_data.get("note", ""),
                )
            except TradeError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Операция выполнена")
                return redirect("portfolio:detail", pk=portfolio.pk)
        return render(
            request,
            self.template_name,
            {
                "portfolio": portfolio,
                "valuation": portfolio_valuation(portfolio),
                "transactions": Transaction.objects.filter(portfolio=portfolio)
                .select_related("share")[:100],
                "trade_form": form,
            },
        )


class PortfolioDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        portfolio = _owned_portfolio(request, pk)
        portfolio.delete()
        messages.success(request, "Портфель удалён")
        return redirect("portfolio:index")
