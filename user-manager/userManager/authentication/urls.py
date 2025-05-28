
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('validate/', views.validate_token, name='validate_token'),
    path('profile/', views.user_profile, name='user_profile'),
    path('health/', views.health_check, name='health_check'),
    path('stats/', views.security_stats, name='security_stats'),
]
