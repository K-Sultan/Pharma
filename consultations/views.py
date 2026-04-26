from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def consultation_list_view(request):
    return render(request, 'consultations/consultation_list.html')