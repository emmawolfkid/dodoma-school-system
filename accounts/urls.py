from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    signup_view, login_view, dashboard_view, logout_view, admin_force_reset_view,
    force_password_change_view, staff_directory, staff_profile_detail, edit_staff_profile,
)

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', logout_view, name='logout'),

    # 👥 STAFF / HR DIRECTORY
    path('staff/', staff_directory, name='staff_directory'),
    path('staff/<int:user_id>/', staff_profile_detail, name='staff_profile_detail'),
    path('staff/<int:user_id>/edit/', edit_staff_profile, name='edit_staff_profile'),

    # 🔐 PASSWORD RESET (EMAIL)
    path('forgot-password/', auth_views.PasswordResetView.as_view(
        template_name='accounts/forgot_password.html'
    ), name='password_reset'),

    path('reset-sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/reset_sent.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/reset_confirm.html'
    ), name='password_reset_confirm'),

    path('reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/reset_complete.html'
    ), name='password_reset_complete'),

    # 🔥 ADMIN RESET
    path('admin-force-reset/<int:user_id>/', admin_force_reset_view, name='admin_force_reset'),

    # 🔥 FORCE USER TO CHANGE PASSWORD
    path('force-change-password/', force_password_change_view, name='force_change_password'),
]