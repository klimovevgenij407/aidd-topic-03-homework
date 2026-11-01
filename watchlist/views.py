from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, View

from watchlist.forms import PriceAlertForm, WatchlistForm, WatchlistItemForm
from watchlist.models import Notification, PriceAlert, Watchlist, WatchlistItem
from watchlist.services import rearm_alert


def _owned_watchlist(request, pk: int) -> Watchlist:
    return get_object_or_404(Watchlist, pk=pk, user=request.user)


def _watchlists_with_counts(user):
    return Watchlist.objects.filter(user=user).annotate(
        item_count=Count("items", distinct=True),
        active_alert_count=Count(
            "items__alerts",
            filter=Q(items__alerts__is_active=True),
            distinct=True,
        ),
    )


class WatchlistIndexView(LoginRequiredMixin, View):
    """Список наблюдения: перечень списков и создание нового."""

    template_name = "watchlist/index.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "watchlists": _watchlists_with_counts(request.user),
                "form": WatchlistForm(),
            },
        )

    def post(self, request):
        form = WatchlistForm(request.POST)
        if form.is_valid():
            watchlist = form.save(commit=False)
            watchlist.user = request.user
            watchlist.save()
            messages.success(request, "Список наблюдения создан")
            return redirect("watchlist:detail", pk=watchlist.pk)
        return render(
            request,
            self.template_name,
            {"watchlists": _watchlists_with_counts(request.user), "form": form},
        )


class WatchlistDetailView(LoginRequiredMixin, View):
    """Состав списка, добавление акций и целевых цен."""

    template_name = "watchlist/detail.html"

    def _context(self, request, watchlist, item_form=None):
        items = (
            WatchlistItem.objects.filter(watchlist=watchlist)
            .select_related("share")
            .prefetch_related("alerts")
        )
        return {
            "watchlist": watchlist,
            "items": items,
            "item_form": item_form or WatchlistItemForm(),
            "alert_form": PriceAlertForm(),
        }

    def get(self, request, pk):
        watchlist = _owned_watchlist(request, pk)
        return render(request, self.template_name, self._context(request, watchlist))

    def post(self, request, pk):
        watchlist = _owned_watchlist(request, pk)
        form = WatchlistItemForm(request.POST)
        if form.is_valid():
            share = form.cleaned_data["share"]
            if WatchlistItem.objects.filter(watchlist=watchlist, share=share).exists():
                form.add_error("share", "Эта акция уже есть в списке")
            else:
                item = form.save(commit=False)
                item.watchlist = watchlist
                item.save()
                messages.success(request, f"{share.ticker} добавлена в список")
                return redirect("watchlist:detail", pk=watchlist.pk)
        return render(
            request, self.template_name, self._context(request, watchlist, form)
        )


class WatchlistDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        watchlist = _owned_watchlist(request, pk)
        watchlist.delete()
        messages.success(request, "Список наблюдения удалён")
        return redirect("watchlist:index")


class WatchlistItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(
            WatchlistItem, pk=pk, watchlist__user=request.user
        )
        watchlist_pk = item.watchlist_id
        item.delete()
        messages.success(request, "Акция удалена из списка")
        return redirect("watchlist:detail", pk=watchlist_pk)


class PriceAlertCreateView(LoginRequiredMixin, View):
    def post(self, request, item_pk):
        item = get_object_or_404(
            WatchlistItem, pk=item_pk, watchlist__user=request.user
        )
        form = PriceAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.item = item
            alert.save()
            messages.success(request, "Целевая цена добавлена")
        else:
            messages.error(request, "Не удалось добавить целевую цену: проверьте поля")
        return redirect("watchlist:detail", pk=item.watchlist_id)


class PriceAlertToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        alert = get_object_or_404(
            PriceAlert, pk=pk, item__watchlist__user=request.user
        )
        if alert.is_active:
            alert.is_active = False
            alert.save(update_fields=["is_active"])
            messages.info(request, "Целевая цена отключена")
        else:
            rearm_alert(alert)
            messages.success(request, "Целевая цена снова активна")
        return redirect("watchlist:detail", pk=alert.item.watchlist_id)


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "watchlist/notifications.html"
    context_object_name = "notifications"
    paginate_by = 50

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related(
            "alert__item__share"
        )

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        messages.success(request, "Все уведомления отмечены прочитанными")
        return redirect("watchlist:notifications")


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
        return redirect("watchlist:notifications")
