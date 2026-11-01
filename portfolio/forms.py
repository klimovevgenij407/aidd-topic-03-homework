from django import forms
from django.core.exceptions import ValidationError

from portfolio.models import Portfolio, PortfolioTransaction
from portfolio.services import validate_transaction


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ("name", "base_currency")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Мой портфель"}),
            "base_currency": forms.TextInput(attrs={"placeholder": "rub"}),
        }


class PortfolioTransactionForm(forms.ModelForm):
    def __init__(self, *args, portfolio: Portfolio | None = None, **kwargs):
        self.portfolio = portfolio
        super().__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs["step"] = "0.000001"
        self.fields["price"].widget.attrs["step"] = "0.000000001"
        self.fields["commission"].widget.attrs["step"] = "0.000000001"

    class Meta:
        model = PortfolioTransaction
        fields = (
            "share",
            "side",
            "quantity",
            "price",
            "commission",
            "executed_at",
            "note",
        )
        widgets = {
            "executed_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "quantity": forms.NumberInput(attrs={"step": "0.000001"}),
            "price": forms.NumberInput(attrs={"step": "0.01"}),
            "commission": forms.NumberInput(attrs={"step": "0.01"}),
        }
        labels = {
            "share": "Акция",
            "side": "Операция",
            "quantity": "Количество",
            "price": "Цена за единицу",
            "commission": "Комиссия",
            "executed_at": "Дата и время",
            "note": "Комментарий",
        }

    def clean(self):
        cleaned_data = super().clean()
        share = cleaned_data.get("share")
        side = cleaned_data.get("side")
        quantity = cleaned_data.get("quantity")
        executed_at = cleaned_data.get("executed_at")
        if self.portfolio and share and side and quantity and executed_at:
            try:
                validate_transaction(
                    self.portfolio,
                    share,
                    side,
                    quantity,
                    executed_at,
                    exclude_pk=self.instance.pk,
                )
            except ValidationError as exc:
                self.add_error(None, exc)
        return cleaned_data

    def save(self, commit: bool = True):
        transaction = super().save(commit=False)
        if self.portfolio:
            transaction.portfolio = self.portfolio
        if commit:
            transaction.save()
            self.save_m2m()
        return transaction
