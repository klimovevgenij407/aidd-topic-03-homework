from django import forms

from .models import Share


class ShareForm(forms.ModelForm):
    """Пользовательская форма акции.

    Служебные поля (uid, last_price, is_trend_high, updated_at) управляются
    приложением и не должны редактироваться вручную.
    """

    class Meta:
        model = Share
        fields = (
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
        )
        widgets = {
            "figi": forms.TextInput(attrs={"placeholder": "BBG000000001"}),
            "isin": forms.TextInput(attrs={"placeholder": "RU0000000001"}),
            "name": forms.TextInput(attrs={"placeholder": "Название компании"}),
            "ticker": forms.TextInput(attrs={"placeholder": "SBER"}),
            "currency": forms.TextInput(attrs={"placeholder": "rub"}),
        }

    def clean_ticker(self):
        return self.cleaned_data["ticker"].strip().upper()

    def clean_figi(self):
        return self.cleaned_data["figi"].strip()

    def clean_isin(self):
        return self.cleaned_data["isin"].strip().upper()

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().lower()
