from rest_framework.generics import GenericAPIView
from rest_framework import serializers
from rest_framework.views import APIView

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import build_serializer_context


class StatusAwareJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.users.authentication.StatusAwareJWTAuthentication"
    name = "Bearer"

    def get_security_definition(self, _auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }


class EmptyAPIViewPayloadSerializer(serializers.Serializer):
    pass


class ProjectAutoSchema(AutoSchema):
    """Project defaults for APIViews that intentionally return ad-hoc payloads."""

    def _get_serializer(self):
        view = self.view
        if isinstance(view, APIView) and not isinstance(view, GenericAPIView):
            context = build_serializer_context(view)
            if callable(getattr(view, "get_serializer", None)):
                return view.get_serializer(context=context)
            if callable(getattr(view, "get_serializer_class", None)):
                return view.get_serializer_class()(context=context)
            if hasattr(view, "serializer_class"):
                return view.serializer_class
            return EmptyAPIViewPayloadSerializer(context=context)

        return super()._get_serializer()
