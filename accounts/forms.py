"""Forms used by platform administrators to manage authenticated users."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import UserType


User = get_user_model()


class SystemManagementUserForm(forms.ModelForm):
    """Provision a new platform user with role assignment and password validation."""

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Use a strong password that meets Django security rules.",
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    grant_staff_access = forms.BooleanField(
        label="Allow admin-site access",
        required=False,
        initial=False,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "user_type", "is_active")
        widgets = {
            "first_name": forms.TextInput(),
            "last_name": forms.TextInput(),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        labels = {
            "user_type": "Role",
            "is_active": "Active account",
        }

    def __init__(self, *args, **kwargs):
        """Load role options in a stable order for the create-user form."""

        super().__init__(*args, **kwargs)
        self.fields["user_type"].queryset = UserType.objects.order_by("name")
        self.fields["user_type"].required = False

    def clean_email(self):
        """Normalize and validate email uniqueness for the custom user model."""

        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        """Ensure password confirmation matches and passes validation."""

        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two password fields must match.")

        if password1:
            candidate = User(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password1, candidate)
            except ValidationError as error:
                self.add_error("password1", error)

        return cleaned_data

    def save(self, commit=True):
        """Create the user, set their password, and derive safe staff defaults."""

        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = self.cleaned_data["grant_staff_access"] or getattr(user.user_type, "code", "") == "admin"
        user.is_superuser = False
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
        return user
