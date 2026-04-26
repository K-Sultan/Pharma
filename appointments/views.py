from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required
def appointment_list_view(request):
    return render(request, 'appointments/appointment_list.html')