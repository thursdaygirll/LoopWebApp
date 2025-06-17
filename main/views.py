from django.shortcuts import render

def login_view(request):
    return render(request, 'main/login.html')

def dashboard_view(request):
    return render(request, 'main/dashboard.html')

def profile_view(request):
    return render(request, 'main/profile.html')