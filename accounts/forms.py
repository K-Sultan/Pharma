from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import DoctorScheduleException, DoctorScheduleExceptionType, DoctorWeeklySchedule, UserRole


User = get_user_model()


class PatientRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class DoctorCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    license_number = forms.CharField(max_length=100)
    specialization = forms.CharField(max_length=120)
    department = forms.CharField(max_length=120, required=False)
    bio = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.DOCTOR
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ReceptionistCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    department = forms.CharField(max_length=120, required=False)
    phone_extension = forms.CharField(max_length=10, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.RECEPTIONIST
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class DoctorWeeklyScheduleForm(forms.ModelForm):
    class Meta:
        model = DoctorWeeklySchedule
        fields = ['day', 'start_time', 'end_time']


class DoctorScheduleExceptionForm(forms.ModelForm):
    class Meta:
        model = DoctorScheduleException
        fields = ['date', 'exception_type', 'start_time', 'end_time', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class DoctorDayScheduleForm(forms.Form):
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('Start time must be earlier than end time.')
        return cleaned_data


class DoctorDayOffExceptionForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d'],
    )

    class Meta:
        model = DoctorScheduleException
        fields = ['date', 'note']

    def __init__(self, *args, **kwargs):
        self.doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        self.instance.exception_type = DoctorScheduleExceptionType.UNAVAILABLE
        self.instance.start_time = None
        self.instance.end_time = None

    def clean_date(self):
        date = self.cleaned_data['date']
        if date < timezone.localdate():
            raise forms.ValidationError('Date cannot be in the past.')
        if self.doctor and DoctorScheduleException.objects.filter(doctor=self.doctor, date=date).exists():
            raise forms.ValidationError('An exception already exists for this date.')
        return date

    def save(self, commit=True):
        schedule_exception = super().save(commit=False)
        schedule_exception.exception_type = DoctorScheduleExceptionType.UNAVAILABLE
        schedule_exception.start_time = None
        schedule_exception.end_time = None
        if commit:
            schedule_exception.save()
        return schedule_exception


class DoctorCustomWorkDayExceptionForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d'],
    )

    class Meta:
        model = DoctorScheduleException
        fields = ['date', 'start_time', 'end_time', 'note']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        self.doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        self.instance.exception_type = DoctorScheduleExceptionType.AVAILABLE

    def clean_date(self):
        date = self.cleaned_data['date']
        if date < timezone.localdate():
            raise forms.ValidationError('Date cannot be in the past.')
        if self.doctor and DoctorScheduleException.objects.filter(doctor=self.doctor, date=date).exists():
            raise forms.ValidationError('An exception already exists for this date.')
        return date

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('Custom work day start time must be earlier than end time.')
        return cleaned_data

    def save(self, commit=True):
        schedule_exception = super().save(commit=False)
        schedule_exception.exception_type = DoctorScheduleExceptionType.AVAILABLE
        if commit:
            schedule_exception.save()
        return schedule_exception