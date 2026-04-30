from datetime import datetime, timedelta
from accounts.models import DoctorWeeklySchedule, DoctorScheduleException
from .models import Appointment, AppointmentStatus

def generate_slots(start_time, end_time, duration=30):
    slots = []
    current = datetime.combine(datetime.today(), start_time)
    end = datetime.combine(datetime.today(), end_time)

    while current + timedelta(minutes=duration) <= end:
        slot_start = current.time()
        slot_end = (current + timedelta(minutes=duration)).time()

        slots.append((slot_start, slot_end))
        current += timedelta(minutes=duration)

    return slots



def get_available_slots(doctor, date, exclude_appointment_id=None):
    weekday = date.weekday()

    # Check exception first
    exception = DoctorScheduleException.objects.filter(
        doctor=doctor,
        date=date
    ).first()

    if exception:
        if exception.exception_type == "unavailable":
            return []

        start_time = exception.start_time
        end_time = exception.end_time

    else:
        schedule = DoctorWeeklySchedule.objects.filter(
            doctor=doctor,
            day=weekday
        ).first()

        if not schedule:
            return []

        start_time = schedule.start_time
        end_time = schedule.end_time

    # Generate all slots
    all_slots = generate_slots(start_time, end_time)

    # Get booked slots
    booked = Appointment.objects.filter(
        doctor=doctor,
        date=date
    ).exclude(status=AppointmentStatus.CANCELLED)

    if exclude_appointment_id is not None:
        booked = booked.exclude(id=exclude_appointment_id)

    booked = booked.values_list("start_time", flat=True)

    # Filter available
    available = [
        (s, e) for s, e in all_slots if s not in booked
    ]

    return available