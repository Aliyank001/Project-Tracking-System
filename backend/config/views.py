import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


@require_GET
@never_cache
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
@csrf_protect
@never_cache
def sign_in(request):
    try:
        credentials = json.loads(request.body)
    except ValueError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)

    if not isinstance(credentials, dict):
        return JsonResponse({"detail": "Expected a JSON object."}, status=400)

    username = credentials.get("username")
    password = credentials.get("password")
    if (
        not isinstance(username, str)
        or not username.strip()
        or not isinstance(password, str)
        or not password
    ):
        return JsonResponse({"detail": "Username and password are required."}, status=400)

    user = authenticate(request, username=username.strip(), password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid username or password."}, status=401)

    login(request, user)
    return JsonResponse({"username": user.get_username(), "csrfToken": get_token(request)})


@require_POST
@csrf_protect
@never_cache
def sign_out(request):
    logout(request)
    return HttpResponse(status=204)


@never_cache
@api_view(["GET"])
def current_user(request):
    user = request.user
    return Response({
        "id": user.pk,
        "username": user.get_username(),
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "permissions": sorted(user.get_all_permissions()),
    })
