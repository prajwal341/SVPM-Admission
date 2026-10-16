from django.contrib import admin
from django.urls import include, path
from admissions.views import csrf_cookie, health

urlpatterns = [path("admin/", admin.site.urls), path("api/health/", health), path("api/csrf/", csrf_cookie), path("api/", include("admissions.urls"))]
