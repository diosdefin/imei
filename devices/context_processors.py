from __future__ import annotations

from .utils import can_delete_devices, is_admin, is_operator, is_super_admin

def role_flags(request):
    user = getattr(request, 'user', None)
    return {
        'role_is_admin': is_admin(user),
        'role_is_operator': is_operator(user),
        'role_is_super_admin': is_super_admin(user),
        'role_can_delete': can_delete_devices(user),
    }