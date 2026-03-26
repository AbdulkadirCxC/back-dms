from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .audit import get_client_ip
from .models import AuditLog
from .serializers import UserListSerializer, UserRegisterSerializer

User = get_user_model()


class CurrentUserView(APIView):
    """
    GET /api/auth/me/ - Current logged-in user for header/sidebar.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserListSerializer(request.user)
        return Response(serializer.data)


class TokenObtainPairWithLogView(TokenObtainPairView):
    """JWT token + login audit log."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                username = request.data.get('username', '')
                user = User.objects.filter(username__iexact=username).first()
                ip = get_client_ip(request)
                AuditLog.objects.create(
                    user=user,
                    action='login',
                    path=request.path,
                    method=request.method,
                    resource='auth',
                    object_repr=f'Login: {username}',
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                )
            except Exception:
                pass
        return response


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
