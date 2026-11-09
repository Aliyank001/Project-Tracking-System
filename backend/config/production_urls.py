from django.conf import settings
from django.http import FileResponse
from django.urls import path
from django.views.decorators.http import require_safe

from .urls import urlpatterns as api_and_admin_patterns


@require_safe
def frontend(request):
    response = FileResponse((settings.FRONTEND_DIST / "index.html").open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    return response


urlpatterns = [path("", frontend, name="frontend"), *api_and_admin_patterns]
