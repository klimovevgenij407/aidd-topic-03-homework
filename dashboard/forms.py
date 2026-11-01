from django import forms

from .models import Share


class ShareModelForm(forms.ModelForm):
    """Инструмент"""

    class Meta:
        model = Share
        fields = ("figi", "isin", "name", "ticker", "currency", "uid")
