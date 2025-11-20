import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'imei_manager.settings')
django.setup()

from django.contrib.auth import get_user_model
from devices.models import UserProfile

User = get_user_model()

def set_super_admin(username):
    try:
        user = User.objects.get(username=username)
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.is_super_admin = True
        profile.role = UserProfile.Roles.ADMIN
        profile.save()
        print(f"Пользователь {username} назначен суперадминистратором")
    except User.DoesNotExist:
        print(f"Пользователь {username} не найден")

if __name__ == "__main__":
    # Замените 'admin' на имя вашего пользователя
    set_super_admin('asus')