from django import forms
from django.contrib.auth import get_user_model
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row, Submit
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Device, UserProfile

User = get_user_model()


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['imei', 'model_name', 'status', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = Device.PUBLIC_STATUS_CHOICES
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('imei', css_class='col-12 col-md-6'),
                Column('model_name', css_class='col-12 col-md-6'),
            ),
            Row(
                Column('status', css_class='col-12 col-md-6'),
                Column('comment', css_class='col-12'),
            ),
            Submit('submit', 'Сохранить', css_class='btn btn-primary w-100'),
        )


class DeviceFilterForm(forms.Form):
    search = forms.CharField(required=False, label='Поиск')
    status = forms.ChoiceField(
        required=False,
        label='Статус',
        choices=[('', 'Все статусы'), *Device.STATUS_CHOICES],
    )
    added_by = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Кто добавил',
    )
    date_from = forms.DateField(required=False, label='Дата с', widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, label='Дата по', widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['added_by'].queryset = User.objects.order_by('username')
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label
            if name == 'status':
                field.widget.attrs['class'] = 'form-select'
            if name == 'added_by':
                field.widget.attrs['class'] = 'form-select'


class DeviceStatusForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = Device.PUBLIC_STATUS_CHOICES


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role', 'can_delete_devices']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'can_delete_devices': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким логином уже существует')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже существует')
        return email