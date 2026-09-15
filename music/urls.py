from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("refresh/", views.refresh, name="refresh"),
    path("profile/", views.profile, name="profile"),
    path("account/", views.account, name="account"),
    path("decision/<uuid:target_id>/", views.decision, name="decision"),
    path("reset-feed/", views.reset_feed, name="reset_feed"),
    path("matches/", views.matches, name="matches"),
    path("chat/<uuid:match_id>/", views.chat, name="chat"),
    path("chat/<uuid:match_id>/messages/", views.chat_messages, name="chat_messages"),
    path("health/", views.health, name="health"),
    path("api/health", views.health, name="api_health"),
]
