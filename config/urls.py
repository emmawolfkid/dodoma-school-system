"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView

# Custom Admin Branding - Removing "Django" naming for a professional look
admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE

urlpatterns = [
    path('', lambda request: redirect('accounts/login/'), name='root'),
    path('portal-admin-access/', admin.site.urls),  # Obscured admin path
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.png')), # Global Favicon
    path('accounts/', include('accounts.urls')),
    path('registration/', include('registration.urls')), # This needs to be uncommented or re-added if it was removed
    path('discipline/', include('discipline.urls')),
    path('academic/', include('academic.urls')),
    path('certificate/', include('certificate.urls')),
    path('audit/', include('audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
