from django.shortcuts import render, redirect
from .forms import SignupForm
from .models import UserModule
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_approved = False
            user.save()

            modules = form.cleaned_data['modules']

            for module in modules:
                UserModule.objects.create(
                    user=user,
                    module=module,
                    is_approved=False
                )

            return redirect('login')
    else:
        form = SignupForm()

    return render(request, 'accounts/signup.html', {'form': form})



def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:

            # 🔥 BLOCK UNAPPROVED USERS
            if not user.is_approved:
                messages.error(request, "Your account is not approved yet.")
                return redirect('login')

            # 🔥 CHECK MODULE APPROVAL
            has_approved_module = UserModule.objects.filter(
                user=user,
                is_approved=True
            ).exists()

            if not has_approved_module and not user.is_superuser:
                messages.error(request, "Your module access is not approved yet.")
                return redirect('login')

            login(request, user)
            return redirect('dashboard')

        else:
            messages.error(request, 'Invalid credentials')

    return render(request, 'accounts/login.html')

from accounts.models import Module, UserModule

@login_required
def dashboard_view(request):

    # 🔥 SYSTEM ADMIN (SUPERUSER)
    if request.user.is_superuser:
        modules = Module.objects.all()
        return render(request, 'accounts/dashboard.html', {
            'modules': modules,
            'is_superuser': True
        })

    # 🔥 NORMAL USERS
    user_modules = UserModule.objects.filter(
        user=request.user,
        is_approved=True
    )


    return render(request, 'accounts/dashboard.html', {
        'user_modules': user_modules
    })


def logout_view(request):
    logout(request)
    return redirect('login')