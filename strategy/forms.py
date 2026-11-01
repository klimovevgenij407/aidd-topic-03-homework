from django import forms

from strategy.models import Strategy


class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = (
            "name",
            "share",
            "buy_below",
            "sell_above",
            "initial_cash",
            "quantity",
            "is_active",
        )
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Моя стратегия"}),
            "buy_below": forms.NumberInput(attrs={"step": "0.01"}),
            "sell_above": forms.NumberInput(attrs={"step": "0.01"}),
            "initial_cash": forms.NumberInput(attrs={"step": "0.01"}),
            "quantity": forms.NumberInput(attrs={"step": "0.000001"}),
        }
        labels = {
            "name": "Название",
            "share": "Акция",
            "buy_below": "Покупать при цене не выше",
            "sell_above": "Продавать при цене не ниже",
            "initial_cash": "Начальный капитал",
            "quantity": "Размер сделки (пусто — весь капитал)",
            "is_active": "Стратегия активна",
        }

    def clean(self):
        cleaned_data = super().clean()
        buy_below = cleaned_data.get("buy_below")
        sell_above = cleaned_data.get("sell_above")
        if buy_below and sell_above and buy_below >= sell_above:
            self.add_error(
                "sell_above",
                "Цена продажи должна быть выше цены покупки.",
            )
        return cleaned_data
