from django import forms
from django.core.validators import MinValueValidator

from dashboard.models import Share
from market.services import latest_price
from portfolio.models import Portfolio


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ("name", "initial_cash")
        widgets = {
            "initial_cash": forms.NumberInput(
                attrs={"step": "0.01", "min": "0"}
            )
        }
        initial = {"initial_cash": 100000}


class TradeForm(forms.Form):
    share = forms.ModelChoiceField(
        queryset=Share.objects.order_by("name"), label="Акция"
    )
    side = forms.ChoiceField(
        choices=(("buy", "Покупка"), ("sell", "Продажа")), label="Операция"
    )
    quantity = forms.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=0.000001,
        label="Количество",
        widget=forms.NumberInput(attrs={"step": "0.000001", "min": "0.000001"}),
    )
    price = forms.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=0.000001,
        required=False,
        label="Цена",
        help_text="Если не указана, используется последняя рыночная цена",
        widget=forms.NumberInput(attrs={"step": "0.000001", "placeholder": "по рынку"}),
    )
    note = forms.CharField(required=False, max_length=255, label="Комментарий")

    def clean(self):
        cleaned_data = super().clean()
        share = cleaned_data.get("share")
        price = cleaned_data.get("price")
        if price is None and share is not None:
            market_price = latest_price(share)
            if market_price is None:
                self.add_error(
                    "price", "Нет рыночной цены — укажите цену операции вручную"
                )
            else:
                cleaned_data["price"] = market_price
        return cleaned_data
