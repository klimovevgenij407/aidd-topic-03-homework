from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

User = get_user_model()


class RegistrationForm(forms.Form):
    """Форма регистрации пользователя по e-mail."""

    email = forms.EmailField(
        required=True,
        label="E-mail",
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )
    password1 = forms.CharField(
        required=True,
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
    password2 = forms.CharField(
        required=True,
        label="Повторите пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control my-3 p-4",
                "placeholder": "Повторите пароль",
            }
        ),
    )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if (
            User.objects.filter(username__iexact=email).exists()
            or User.objects.filter(email__iexact=email).exists()
        ):
            raise ValidationError(
                "Данный e-mail уже зарегистрирован! Введите другой e-mail или "
                "воспользуйтесь формой авторизации."
            )
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        email = cleaned_data.get("email")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Введённые пароли не совпадают.")

        if password1 and email:
            candidate = User(username=email, email=email)
            try:
                password_validation.validate_password(password1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password1"]
        return User.objects.create_user(
            username=email,
            email=email,
            password=password,
        )


class AuthForm(forms.Form):
    """Форма входа по e-mail."""

    email = forms.EmailField(
        required=True,
        label="E-mail",
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )
    password = forms.CharField(
        required=True,
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()
