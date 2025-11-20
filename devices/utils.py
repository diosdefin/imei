from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Device, DeviceHistory, UserProfile

User = get_user_model()



def _safe_profile(user: User) -> UserProfile | None:
    if not user or not user.is_authenticated:
        return None
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


def get_user_profile(user: User) -> UserProfile:
    if not user or not user.is_authenticated:
        raise ValueError('Невозможно получить профиль анонимного пользователя.')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def is_admin(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = _safe_profile(user)
    return profile.role == UserProfile.Roles.ADMIN if profile else False


def is_operator(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_admin_or_super(user):
        return True
    profile = _safe_profile(user)
    return profile.role == UserProfile.Roles.OPERATOR if profile else False



def is_guest(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_operator(user):
        return True
    profile = _safe_profile(user)
    return profile.role == UserProfile.Roles.GUEST if profile else False


def can_delete_devices(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_admin_or_super(user):  # Админы и суперадмины могут удалять
        return True
    profile = _safe_profile(user)
    return bool(profile and profile.role == UserProfile.Roles.OPERATOR and profile.can_delete_devices)

def log_device_history(
    device: Device,
    changed_by: Optional[User],
    previous_status: str,
    new_status: str,
    previous_comment: str | None,
    new_comment: str | None,
) -> None:
    if previous_status == new_status and (previous_comment or '') == (new_comment or ''):
        return
    with transaction.atomic():
        DeviceHistory.objects.create(
            device=device,
            changed_by=changed_by,
            previous_status=previous_status,
            new_status=new_status,
            previous_comment=previous_comment or '',
            new_comment=new_comment or '',
        )

def is_super_admin(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = _safe_profile(user)
    return profile.is_super_admin if profile else False

def is_admin_or_super(user: User) -> bool:
    return is_admin(user) or is_super_admin(user)

def can_manage_users(user: User) -> bool:
    return is_super_admin(user) or is_admin(user)        

