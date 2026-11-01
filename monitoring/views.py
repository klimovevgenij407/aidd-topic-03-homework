"""Views for watchlists and notifications."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from monitoring.forms import WatchlistForm, WatchlistItemForm
from monitoring.models import Notification, Watchlist, WatchlistItem
from monitoring.services import mark_all_read


class UserWatchlistMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class WatchlistListView(LoginRequiredMixin, ListView):
    model = Watchlist
    template_name = "monitoring/watchlist_list.html"
    context_object_name = "watchlists"
    paginate_by = 20

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).prefetch_related(
            "items"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_count"] = self.request.user.notifications.filter(
            is_read=False
        ).count()
        return context


class WatchlistDetailView(UserWatchlistMixin, DetailView):
    model = Watchlist
    template_name = "monitoring/watchlist_detail.html"
    context_object_name = "watchlist"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = self.object.items.select_related("share").all()
        context["item_form"] = WatchlistItemForm(watchlist=self.object)
        return context


class WatchlistCreateView(LoginRequiredMixin, CreateView):
    model = Watchlist
    form_class = WatchlistForm
    template_name = "monitoring/watchlist_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Список наблюдения создан.")
        return super().form_valid(form)


class WatchlistUpdateView(UserWatchlistMixin, UpdateView):
    model = Watchlist
    form_class = WatchlistForm
    template_name = "monitoring/watchlist_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Список наблюдения сохранён.")
        return super().form_valid(form)


class WatchlistDeleteView(UserWatchlistMixin, DeleteView):
    model = Watchlist
    template_name = "monitoring/watchlist_confirm_delete.html"
    context_object_name = "watchlist"
    success_url = reverse_lazy("monitoring:watchlist_list")

    def form_valid(self, form):
        messages.success(self.request, "Список наблюдения удалён.")
        return super().form_valid(form)


class WatchlistItemCreateView(LoginRequiredMixin, CreateView):
    model = WatchlistItem
    form_class = WatchlistItemForm
    template_name = "monitoring/watchlist_item_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.watchlist = get_object_or_404(
                Watchlist,
                pk=kwargs["watchlist_pk"],
                user=request.user,
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["watchlist"] = self.watchlist
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["watchlist"] = self.watchlist
        return context

    def form_valid(self, form):
        form.instance.watchlist = self.watchlist
        messages.success(self.request, "Акция добавлена в список наблюдения.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("monitoring:watchlist_detail", args=[self.watchlist.pk])


class WatchlistItemUpdateView(LoginRequiredMixin, UpdateView):
    model = WatchlistItem
    form_class = WatchlistItemForm
    template_name = "monitoring/watchlist_item_form.html"

    def get_queryset(self):
        return WatchlistItem.objects.filter(
            watchlist__user=self.request.user
        ).select_related("watchlist", "share")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["watchlist"] = self.object.watchlist
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["watchlist"] = self.object.watchlist
        return context

    def form_valid(self, form):
        messages.success(self.request, "Условие наблюдения сохранено.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "monitoring:watchlist_detail",
            args=[self.object.watchlist_id],
        )


class WatchlistItemDeleteView(LoginRequiredMixin, DeleteView):
    model = WatchlistItem
    template_name = "monitoring/watchlist_item_confirm_delete.html"
    context_object_name = "item"

    def get_queryset(self):
        return WatchlistItem.objects.filter(watchlist__user=self.request.user)

    def get_success_url(self):
        messages.success(self.request, "Акция удалена из списка наблюдения.")
        return reverse(
            "monitoring:watchlist_detail",
            args=[self.object.watchlist_id],
        )


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "monitoring/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 50

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).select_related(
            "share", "watchlist_item__watchlist"
        )
        if self.request.GET.get("unread") == "1":
            queryset = queryset.filter(is_read=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unread_count"] = self.request.user.notifications.filter(
            is_read=False
        ).count()
        context["unread_only"] = self.request.GET.get("unread") == "1"
        return context


class NotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return redirect("monitoring:notification_list")


class NotificationReadAllView(LoginRequiredMixin, View):
    def post(self, request):
        count = mark_all_read(request.user)
        messages.success(request, f"Отмечено прочитанными: {count}.")
        return redirect("monitoring:notification_list")
