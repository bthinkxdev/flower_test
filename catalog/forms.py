"""Django forms for the catalog app."""

from __future__ import annotations

from django import forms


class ReviewForm(forms.Form):
    rating = forms.ChoiceField(
        choices=[(i, i) for i in range(5, 0, -1)],
        widget=forms.RadioSelect,
    )
    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    body = forms.CharField(widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}))