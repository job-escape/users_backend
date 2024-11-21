from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class CustomAuthenticationExtension (SimpleJWTScheme):
    target_class = 'custom.custom_backend.PrefetchedJWTAuthentication'
    name = 'customJwtAuth'
