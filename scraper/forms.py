from django import forms

class URLForm(forms.Form):
    url = forms.URLField(
        label='Product/Company URL',
        widget=forms.URLInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'https://www.trustpilot.com/review/example.com',
        })
    )
    max_reviews = forms.IntegerField(
        required=False,
        initial=20,
        min_value=1,
        max_value=20000,          # you can set this to 5000, 10000, or 20000
        label='Max reviews to scrape',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '20',
        })
    )