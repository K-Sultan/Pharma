from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import UserRole

class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.PATIENT
    
class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.DOCTOR


class IsReceptionist(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.RECEPTIONIST


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRole.ADMIN or request.user.is_superuser