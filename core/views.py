from django.shortcuts import redirect, render

def home(request):
    # Authenticated users have no use for the landing page — send them straight to their dashboard
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    return render(request, 'core/home.html')