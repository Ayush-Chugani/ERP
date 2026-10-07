from django.urls import path
from .views import Login, Refresh, Logout, Me, Csrf
from .security_views import PasswordChange, PasswordReset
app_name="accounts"
security_patterns=[path('password/change/',PasswordChange.as_view()),path('password/reset/',PasswordReset.as_view())]
urlpatterns=[path("login/",Login.as_view(),name="login"),path("refresh/",Refresh.as_view(),name="refresh"),
    path("logout/",Logout.as_view(),name="logout"),path("me/",Me.as_view(),name="me"),path("csrf/",Csrf.as_view(),name="csrf")]+security_patterns
