from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .serializers import UserRegisterSerializer


class RegisterView(generics.CreateAPIView):
    """POST: create a Django user (for JWT login at /api/auth/token/)."""

    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            status=status.HTTP_201_CREATED,
        )
