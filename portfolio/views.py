"""Views for virtual portfolios."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from portfolio.forms import PortfolioForm, PortfolioTransactionForm
from portfolio.models import Portfolio, PortfolioTransaction
from portfolio.services import PortfolioError, calculate_portfolio


class UserPortfolioMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class PortfolioListView(LoginRequiredMixin, ListView):
    model = Portfolio
    template_name = "portfolio/portfolio_list.html"
    context_object_name = "portfolios"
    paginate_by = 20

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user).prefetch_related(
            "transactions"
        )


class PortfolioDetailView(UserPortfolioMixin, DetailView):
    model = Portfolio
    template_name = "portfolio/portfolio_detail.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            summary = calculate_portfolio(self.object)
        except PortfolioError as exc:
            summary = None
            messages.error(self.request, str(exc))
        context["summary"] = summary
        context["transactions"] = self.object.transactions.select_related("share")
        context["form"] = PortfolioTransactionForm(portfolio=self.object)
        return context


class PortfolioCreateView(LoginRequiredMixin, CreateView):
    model = Portfolio
    form_class = PortfolioForm
    template_name = "portfolio/portfolio_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Портфель создан.")
        return super().form_valid(form)


class PortfolioUpdateView(UserPortfolioMixin, UpdateView):
    model = Portfolio
    form_class = PortfolioForm
    template_name = "portfolio/portfolio_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Портфель сохранён.")
        return super().form_valid(form)


class PortfolioDeleteView(UserPortfolioMixin, DeleteView):
    model = Portfolio
    template_name = "portfolio/portfolio_confirm_delete.html"
    context_object_name = "portfolio"
    success_url = reverse_lazy("portfolio:portfolio_list")

    def form_valid(self, form):
        messages.success(self.request, "Портфель удалён.")
        return super().form_valid(form)


class TransactionPortfolioMixin(LoginRequiredMixin):
    def get_portfolio(self) -> Portfolio:
        return get_object_or_404(
            Portfolio,
            pk=self.kwargs["portfolio_pk"],
            user=self.request.user,
        )


class PortfolioTransactionCreateView(TransactionPortfolioMixin, CreateView):
    model = PortfolioTransaction
    form_class = PortfolioTransactionForm
    template_name = "portfolio/transaction_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.portfolio = self.get_portfolio()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["portfolio"] = self.portfolio
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portfolio"] = self.portfolio
        return context

    def form_valid(self, form):
        form.instance.portfolio = self.portfolio
        messages.success(self.request, "Операция добавлена.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("portfolio:portfolio_detail", args=[self.portfolio.pk])


class PortfolioTransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = PortfolioTransaction
    form_class = PortfolioTransactionForm
    template_name = "portfolio/transaction_form.html"

    def get_queryset(self):
        return PortfolioTransaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related("portfolio", "share")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["portfolio"] = self.object.portfolio
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portfolio"] = self.object.portfolio
        return context

    def form_valid(self, form):
        messages.success(self.request, "Операция сохранена.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "portfolio:portfolio_detail",
            args=[self.object.portfolio_id],
        )


class PortfolioTransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = PortfolioTransaction
    template_name = "portfolio/transaction_confirm_delete.html"
    context_object_name = "transaction"

    def get_queryset(self):
        return PortfolioTransaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related("portfolio", "share")

    def get_success_url(self):
        messages.success(self.request, "Операция удалена.")
        return reverse(
            "portfolio:portfolio_detail",
            args=[self.object.portfolio_id],
        )
