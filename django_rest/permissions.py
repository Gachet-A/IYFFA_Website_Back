"""
Custom permission classes for Django REST framework.
Defines access control rules for API endpoints.
"""

from rest_framework import permissions
from .models import User

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    Used for admin-only endpoints like user management and statistics.
    """
    def has_permission(self, request, view):
        """
        Check if the user making the request is an admin.
        Returns True if the user is authenticated and has admin type.
        """
        return request.user and request.user.is_admin()