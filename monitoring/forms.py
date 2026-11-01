from django import forms

from monitoring.models import Watchlist, WatchlistItem


class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ("name",)
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Мой список"})}


class WatchlistItemForm(forms.ModelForm):
    def __init__(self, *args, watchlist: Watchlist | None = None, **kwargs):
        self.watchlist = watchlist
        super().__init__(*args, **kwargs)
        self.fields["target_price"].widget.attrs["step"] = "0.000000001"

    class Meta:
        model = WatchlistItem
        fields = ("share", "target_price", "direction")
        widgets = {
            "target_price": forms.NumberInput(
                attrs={"placeholder": "100.00", "step": "0.01"}
            )
        }
        labels = {
            "share": "Акция",
            "target_price": "Целевая цена",
            "direction": "Условие",
        }

    def clean(self):
        cleaned_data = super().clean()
        share = cleaned_data.get("share")
        if self.watchlist and share:
            duplicates = WatchlistItem.objects.filter(
                watchlist=self.watchlist,
                share=share,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(
                    "share",
                    "Эта акция уже добавлена в список наблюдения.",
                )
        return cleaned_data

    def save(self, commit: bool = True):
        item = super().save(commit=False)
        if self.watchlist:
            item.watchlist = self.watchlist
        if commit:
            item.save()
            self.save_m2m()
        return item
