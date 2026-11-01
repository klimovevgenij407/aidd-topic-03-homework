"""Authentication views."""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View

from .forms import AuthForm, RegistrationForm


def _safe_next(request, default: str = "dashboard:index") -> str:
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default


class AuthView(View):
    """Авторизация."""

    @staticmethod
    def get(request):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            if user is not None:
                login(request, user)
                messages.success(request, "Вы вошли в систему.")
                return redirect(_safe_next(request))
            form.add_error(None, "Неверный логин или пароль! Повторите попытку.")
        return render(request, "user/auth.html", {"form": form})


class RegistrationView(View):
    """Регистрация."""

    @staticmethod
    def get(request):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация завершена.")
            return redirect(_safe_next(request))
        return render(request, "user/registration.html", {"form": form})


class LogoutView(View):
    """Выход."""

    @staticmethod
    def get(request):
        logout(request)
        messages.info(request, "Вы вышли из системы.")
        return redirect("dashboard:index")

    post = get
