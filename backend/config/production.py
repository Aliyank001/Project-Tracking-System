from .settings import *

if DEBUG:
    raise ImproperlyConfigured("Set DJANGO_DEBUG=0 for the production service.")
if not database_url:
    raise ImproperlyConfigured("Set DATABASE_URL to the hosted PostgreSQL connection string.")
if not os.getenv("DJANGO_ALLOWED_HOSTS") or not ALLOWED_HOSTS or any(
    "*" in host or host.startswith(".") for host in ALLOWED_HOSTS
):
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to the exact live hostname.")
if DATABASES["default"]["OPTIONS"]["sslmode"] not in {"require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured("The hosted PostgreSQL database requires TLS.")

ROOT_URLCONF = "config.production_urls"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Vite emits URLs under /static/assets/, alongside Django's /static/admin/.
STATICFILES_DIRS = [("assets", FRONTEND_DIST / "assets")]
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Only the Render edge proxy should reach the production listener.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
