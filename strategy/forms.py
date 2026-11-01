from django import forms

from dashboard.models import Share
from strategy.models import Strategy, StrategyRule


class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = ("name", "share", "initial_cash")
        widgets = {
            "initial_cash": forms.NumberInput(attrs={"step": "0.01", "min": "0"})
        }
        initial = {"initial_cash": 100000}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.order_by("name")


class StrategyRuleForm(forms.ModelForm):
    class Meta:
        model = StrategyRule
        fields = ("side", "condition", "threshold", "quantity")
        widgets = {
            "threshold": forms.NumberInput(
                attrs={"step": "0.000001", "min": "0.000001"}
            ),
            "quantity": forms.NumberInput(
                attrs={"step": "0.000001", "min": "0.000001"}
            ),
        }
