from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignupForm
from .models import UserModule, Module, User
from audit.models import AuditLog
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from academic.utils_notifications import notify_module_admins


# 🔹 HELPER
def get_client_ip(request):
    """
    Only trust X-Forwarded-For when the direct connection comes from a
    local/private-network reverse proxy (nginx, ngrok agent, etc). Otherwise
    an external client could set that header itself and spoof the IP that
    ends up in the login/logout audit trail.
    """
    remote_addr = request.META.get('REMOTE_ADDR', '')
    is_trusted_proxy = (
        remote_addr in ('127.0.0.1', '::1')
        or remote_addr.startswith('10.')
        or remote_addr.startswith('192.168.')
    )

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if is_trusted_proxy and x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return remote_addr


# 🔹 SIGNUP
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
                notify_module_admins(
                    module.name,
                    f"{user.username} has requested access to the {module.name} module and needs approval.",
                    email=True,
                    email_subject="New user pending approval",
                )

            return redirect('login')
    else:
        form = SignupForm()

    return render(request, 'accounts/signup.html', {'form': form})


# 🔹 LOGIN WITH AUDIT + SECURITY
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        ip = get_client_ip(request)

        user = authenticate(request, username=username, password=password)

        if user is not None:

            if not user.is_approved:
                messages.error(request, "Your account is not approved yet.")
                return redirect('login')

            has_approved_module = UserModule.objects.filter(
                user=user,
                is_approved=True
            ).exists()

            if not has_approved_module and not user.is_superuser:
                messages.error(request, "Your module access is not approved yet.")
                return redirect('login')

            login(request, user)

            # 🔥 LOG SUCCESS
            AuditLog.objects.create(
                user=user,
                action='login',
                module='accounts',
                changes={
                    'username': username,
                    'ip_address': ip,
                    'status': 'success',
                }
            )

            # 🔥 FORCE PASSWORD CHANGE
            if getattr(user, 'must_change_password', False):
                return redirect('force_change_password')

            return redirect('dashboard')

        else:
            # 🔥 LOG FAILED LOGIN
            AuditLog.objects.create(
                action='login',
                module='accounts',
                changes={
                    'username': username,
                    'ip_address': ip,
                    'status': 'failed',
                }
            )

            messages.error(request, 'Invalid credentials')

    return render(request, 'accounts/login.html')


# 🔹 DASHBOARD
@login_required
def dashboard_view(request):

    if request.user.is_superuser:
        modules = Module.objects.all()
        return render(request, 'accounts/dashboard.html', {
            'modules': modules,
            'is_superuser': True
        })

    user_modules = UserModule.objects.filter(
        user=request.user,
        is_approved=True
    )

    return render(request, 'accounts/dashboard.html', {
        'user_modules': user_modules
    })


# 🔹 LOGOUT WITH AUDIT
@login_required
def logout_view(request):
    AuditLog.objects.create(
        user=request.user,
        action='logout',
        module='accounts',
        changes={
            'username': request.user.username,
            'ip_address': get_client_ip(request),
        }
    )

    logout(request)
    return redirect('login')


# 🔥 ADMIN FORCE RESET (NO EMAIL USERS)
@login_required
def admin_force_reset_view(request, user_id):
    if not request.user.is_superuser:
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)

    user.must_change_password = True
    user.save()

    AuditLog.objects.create(
        user=user,
        action='update',
        module='accounts',
        model_name='User',
        object_id=str(user.id),
        changes={
            'username': user.username,
            'ip_address': get_client_ip(request),
            'event': 'admin_force_reset',
            'must_change_password': True,
        }
    )

    messages.success(request, f"{user.username} will reset password on next login.")
    return redirect('dashboard')


# 🔐 FORCE PASSWORD CHANGE
@login_required
def force_password_change_view(request):
    if not request.user.must_change_password:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SetPasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save()

            AuditLog.objects.create(
                user=user,
                action='update',
                module='accounts',
                model_name='User',
                object_id=str(user.id),
                changes={
                    'username': user.username,
                    'ip_address': get_client_ip(request),
                    'event': 'password_reset_complete',
                    'must_change_password': False,
                }
            )

            messages.success(request, "Password changed successfully.")
            return redirect('dashboard')
    else:
        form = SetPasswordForm(request.user)

    return render(request, 'accounts/force_change_password.html', {'form': form})
