from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from accounts.decorators import role_required
from accounts.forms import (
    DoctorCustomWorkDayExceptionForm,
    DoctorDayOffExceptionForm,
    DoctorDayScheduleForm,
)
from accounts.models import DoctorProfile, DoctorWeeklySchedule, UserRole, Weekday

@login_required
def dashboard_redirect(request):
    user = request.user

    if user.role == UserRole.ADMIN or user.is_superuser:
        return redirect('admin_dashboard')
    elif user.role == UserRole.DOCTOR:
        return redirect('doctor_dashboard')
    elif user.role == UserRole.RECEPTIONIST:
        return redirect('receptionist_dashboard')
    elif user.role == UserRole.PATIENT:
        return redirect('patient_dashboard')

    return redirect('home')


@login_required
@role_required(UserRole.PATIENT)
def patient_dashboard(request):
    return render(request, 'dashboard/patient_dashboard.html')


@login_required
@role_required(UserRole.DOCTOR)
def doctor_dashboard(request):
    return render(request, 'dashboard/doctor_dashboard.html')


@login_required
@role_required(UserRole.DOCTOR)
def doctor_schedule_view(request):
    doctor_profile = get_object_or_404(DoctorProfile, user=request.user)

    selected_day_raw = request.GET.get('day')
    if selected_day_raw is None:
        selected_day = Weekday.MONDAY
    else:
        try:
            selected_day = int(selected_day_raw)
        except ValueError:
            selected_day = Weekday.MONDAY
    selected_day_values = [day.value for day in Weekday]
    if selected_day not in selected_day_values:
        selected_day = Weekday.MONDAY

    weekly_entries = doctor_profile.weekly_schedule.all()
    weekly_by_day = {entry.day: entry for entry in weekly_entries}

    selected_weekly_entry = weekly_by_day.get(selected_day)
    if selected_weekly_entry:
        day_schedule_form = DoctorDayScheduleForm(
            initial={
                'start_time': selected_weekly_entry.start_time,
                'end_time': selected_weekly_entry.end_time,
            }
        )
    else:
        day_schedule_form = DoctorDayScheduleForm()

    day_off_form = DoctorDayOffExceptionForm(doctor=doctor_profile)
    custom_work_day_form = DoctorCustomWorkDayExceptionForm(doctor=doctor_profile)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_weekly':
            selected_day_raw = request.POST.get('selected_day')
            try:
                selected_day = int(selected_day_raw)
            except (TypeError, ValueError):
                selected_day = Weekday.MONDAY
            if selected_day not in selected_day_values:
                selected_day = Weekday.MONDAY

            day_schedule_form = DoctorDayScheduleForm(request.POST)
            if day_schedule_form.is_valid():
                DoctorWeeklySchedule.objects.update_or_create(
                    doctor=doctor_profile,
                    day=selected_day,
                    defaults={
                        'start_time': day_schedule_form.cleaned_data['start_time'],
                        'end_time': day_schedule_form.cleaned_data['end_time'],
                    },
                )
                messages.success(request, 'Weekly schedule updated.')
                return redirect(f"{redirect('doctor_schedule').url}?day={selected_day}")

        elif action == 'clear_weekly':
            selected_day_raw = request.POST.get('selected_day')
            try:
                selected_day = int(selected_day_raw)
            except (TypeError, ValueError):
                selected_day = Weekday.MONDAY
            if selected_day not in selected_day_values:
                selected_day = Weekday.MONDAY

            DoctorWeeklySchedule.objects.filter(doctor=doctor_profile, day=selected_day).delete()
            messages.success(request, 'Day marked as off in weekly schedule.')
            return redirect(f"{redirect('doctor_schedule').url}?day={selected_day}")

        elif action == 'add_day_off':
            day_off_form = DoctorDayOffExceptionForm(request.POST, doctor=doctor_profile)
            if day_off_form.is_valid():
                schedule_exception = day_off_form.save(commit=False)
                schedule_exception.doctor = doctor_profile
                schedule_exception.save()
                messages.success(request, 'Day off added.')
                return redirect('doctor_schedule')

        elif action == 'add_custom_work_day':
            custom_work_day_form = DoctorCustomWorkDayExceptionForm(request.POST, doctor=doctor_profile)
            if custom_work_day_form.is_valid():
                schedule_exception = custom_work_day_form.save(commit=False)
                schedule_exception.doctor = doctor_profile
                schedule_exception.save()
                messages.success(request, 'Custom work day added.')
                return redirect('doctor_schedule')

        elif action == 'delete_exception':
            exception_id = request.POST.get('exception_id')
            doctor_profile.schedule_exceptions.filter(id=exception_id).delete()
            messages.success(request, 'Schedule exception removed.')
            return redirect('doctor_schedule')

    weekly_rows = [
        {
            'day_value': day.value,
            'day_label': day.label,
            'entry': weekly_by_day.get(day.value),
            'is_selected': day.value == selected_day,
        }
        for day in Weekday
    ]
    exception_entries = doctor_profile.schedule_exceptions.all()

    context = {
        'weekly_rows': weekly_rows,
        'exception_entries': exception_entries,
        'selected_day': selected_day,
        'selected_day_label': Weekday(selected_day).label,
        'selected_weekly_entry': selected_weekly_entry,
        'day_schedule_form': day_schedule_form,
        'day_off_form': day_off_form,
        'custom_work_day_form': custom_work_day_form,
    }
    return render(request, 'dashboard/doctor_schedule.html', context)


@login_required
@role_required(UserRole.RECEPTIONIST)
def receptionist_dashboard(request):
    return render(request, 'dashboard/receptionist_dashboard.html')


@login_required
@role_required(UserRole.ADMIN)
def admin_dashboard(request):
    return render(request, 'dashboard/admin_dashboard.html')