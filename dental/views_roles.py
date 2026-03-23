"""
Roles and Permissions API.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

from .serializers import (
    RoleSerializer,
    RoleCreateUpdateSerializer,
    PermissionSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class UserPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 200


class UserViewSet(viewsets.ModelViewSet):
    """
    User API: list, retrieve, update, delete.
    GET /api/users/?limit=100&ordering=-id
    PATCH /api/users/{id}/ - update user (username, email, is_staff, is_superuser, is_active)
    DELETE /api/users/{id}/ - delete user
    """
    queryset = User.objects.all().prefetch_related('groups')
    permission_classes = [IsAdminUser]
    pagination_class = UserPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ['id', 'username', 'email', 'date_joined', 'is_staff', 'is_active']
    ordering = ['-id']

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserListSerializer


class RoleViewSet(viewsets.ModelViewSet):
    """
    Role (Group) API: create, list, retrieve, update, delete roles.
    Only staff users can manage roles.
    Create payload: { "name": "Receptionist", "permissions": [1, 2, 3] }
    """
    queryset = Group.objects.all().prefetch_related('permissions')
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RoleCreateUpdateSerializer
        return RoleSerializer


@api_view(['GET'])
@permission_classes([IsAdminUser])
def permissions_list(request):
    """
    List all available permissions (for assigning to roles).
    Optionally filter by app: ?content_type__app_label=dental
    """
    qs = Permission.objects.select_related('content_type').all().order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    )
    app_label = request.query_params.get('content_type__app_label')
    if app_label:
        qs = qs.filter(content_type__app_label=app_label)
    serializer = PermissionSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST', 'GET'])
@permission_classes([IsAdminUser])
def user_roles(request, user_id):
    """
    Assign roles to a user.
    POST: { "roles": [1, 2, 3] } - replace user's roles
    GET: return user's current roles
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        roles = user.groups.all()
        return Response(RoleSerializer(roles, many=True).data)

    roles_ids = request.data.get('roles', [])
    if not isinstance(roles_ids, list):
        return Response(
            {'error': 'roles must be a list of role IDs'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    groups = Group.objects.filter(pk__in=roles_ids)
    user.groups.set(groups)
    return Response(RoleSerializer(user.groups.all(), many=True).data)
