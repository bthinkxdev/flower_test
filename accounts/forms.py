"""Django forms for the accounts app."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import Address


class EmailLoginForm(AuthenticationForm):
    """Email/password login form using email as the username field."""

    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "class": "form-control"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": "form-control"}
        ),
    )


class OTPRequestForm(forms.Form):
    """Form to request an OTP for phone-based authentication."""

    phone = forms.CharField(
        max_length=20,
        label="Phone number",
        widget=forms.TextInput(attrs={"autocomplete": "tel"}),
    )
    purpose = forms.ChoiceField(
        choices=[
            ("login", "Login"),
            ("signup", "Sign Up"),
            ("password_reset", "Password Reset"),
        ],
        label="Purpose",
    )


class OTPVerifyForm(forms.Form):
    """Form to verify a submitted OTP code."""

    phone = forms.CharField(max_length=20, label="Phone number")
    otp_code = forms.CharField(max_length=6, min_length=6, label="OTP code")
    purpose = forms.ChoiceField(
        choices=[
            ("login", "Login"),
            ("signup", "Sign Up"),
            ("password_reset", "Password Reset"),
        ],
        label="Purpose",
    )


class EmailRegistrationForm(forms.Form):
    """Form for email-based customer registration."""

    email = forms.EmailField(label="Email")
    password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        label="Password",
    )
    name = forms.CharField(max_length=150, label="Full name")


class GoogleLoginForm(forms.Form):
    """Form accepting a Google ID token from the client."""

    id_token = forms.CharField(widget=forms.HiddenInput)


class GuestCheckoutForm(forms.Form):
    """Form to issue a guest checkout token for a cart session."""

    cart_id = forms.CharField(max_length=64, label="Cart ID")


class ForgotPasswordForm(forms.Form):
    """Form to initiate password reset via OTP."""

    phone = forms.CharField(max_length=20, label="Phone number")


class ResetPasswordForm(forms.Form):
    """Form to set a new password after OTP verification."""

    phone = forms.CharField(max_length=20, label="Phone number")
    otp_code = forms.CharField(max_length=6, min_length=6, label="OTP code")
    new_password = forms.CharField(widget=forms.PasswordInput, min_length=8, label="New password")


class AddressForm(forms.ModelForm):
    """Create or update a customer delivery address."""

    class Meta:
        model = Address
        fields = ("label", "line1", "line2", "city", "is_default")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from delivery.models import City

        self.fields["city"].queryset = City.objects.filter(is_active=True)


class CorporateRegistrationForm(forms.Form):
    """B2B corporate account registration form."""

    email = forms.EmailField(label="Work email")
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Password")
    name = forms.CharField(max_length=150, label="Contact name")
    company_name = forms.CharField(max_length=200, label="Company name")
    trade_license_number = forms.CharField(max_length=100, label="Trade license number")
