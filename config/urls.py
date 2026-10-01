from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from receipts import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("receipts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)