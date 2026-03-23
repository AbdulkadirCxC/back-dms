"""
Custom permission classes for role-based access control.
"""
from rest_framework import permissions


class HasPermission(permissions.BasePermission):
    """
    Check if user has a specific permission (from their roles/groups).
    Usage: HasPermission('dental.view_patient')
    """
    def __init__(self, perm_codename):
        self.perm_codename = perm_codename

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_perm(self.perm_codename)


class HasAnyPermission(permissions.BasePermission):
    """
    Check if user has any of the given permissions.
    Usage: HasAnyPermission(['dental.view_patient', 'dental.add_patient'])
    """
    def __init__(self, perm_codenames):
        self.perm_codenames = perm_codenames

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return any(request.user.has_perm(p) for p in self.perm_codenames)


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read for authenticated users; write for staff only."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff
