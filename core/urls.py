"""
URL configuration for Dental Management System.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from dental.views_auth import RegisterView, TokenObtainPairWithLogView, CurrentUserView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/token/', TokenObtainPairWithLogView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/me/', CurrentUserView.as_view(), name='current_user'),
    path('api/', include('dental.urls')),
]
