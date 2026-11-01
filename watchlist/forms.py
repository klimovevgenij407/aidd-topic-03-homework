from django import forms

from dashboard.models import Share
from watchlist.models import PriceAlert, Watchlist, WatchlistItem


class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ("name",)


class WatchlistItemForm(forms.ModelForm):
    class Meta:
        model = WatchlistItem
        fields = ("share", "note")
        widgets = {"note": forms.TextInput(attrs={"placeholder": "Необязательно"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.order_by("name")


class PriceAlertForm(forms.ModelForm):
    class Meta:
        model = PriceAlert
        fields = ("condition", "target_price")
        widgets = {
            "target_price": forms.NumberInput(
                attrs={"step": "0.000001", "min": "0.000001"}
            )
        }

    def clean_target_price(self):
        target_price = self.cleaned_data["target_price"]
        if target_price <= 0:
            raise forms.ValidationError("Целевая цена должна быть больше нуля")
        return target_price
