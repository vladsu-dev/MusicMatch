from django.urls import include, path

urlpatterns = [
    path("", include("music.urls")),
]

handler400 = "music.views.bad_request"
handler403 = "music.views.permission_denied"
handler404 = "music.views.not_found"
handler500 = "music.views.server_error"
