from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

User = get_user_model()

def luhn_checksum(value: str) -> bool:
    """Validate an IMEI using the Luhn algorithm."""
    digits = [int(d) for d in value]
    checksum = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0

def validate_imei(value: str) -> None:
    if not value.isdigit() or len(value) != 15:
        raise ValidationError("IMEI должен содержать 15 цифр.")
    if not luhn_checksum(value):
        raise ValidationError("IMEI не прошел проверку по алгоритму Луна.")

class Device(models.Model):
    STATUS_IN_STOCK = 'in_stock'
    STATUS_SOLD = 'sold'
    STATUS_WRITTEN_OFF = 'written_off'
    STATUS_TRASH = 'trash'

    STATUS_CHOICES = [
        (STATUS_IN_STOCK, 'В наличии'),
        (STATUS_SOLD, 'Продано'),
        (STATUS_WRITTEN_OFF, 'Списан'),
        (STATUS_TRASH, 'В корзине'),
    ]

    PUBLIC_STATUS_CHOICES = [
        (STATUS_IN_STOCK, 'В наличии'),
        (STATUS_SOLD, 'Продано'),
        (STATUS_WRITTEN_OFF, 'Списан'),
    ]

    imei = models.CharField(
        max_length=15,
        unique=True,
        verbose_name="IMEI",
        validators=[RegexValidator(r'^\d{15}$', "Допустимы только 15 цифр"), validate_imei],
    )
    model_name = models.CharField(max_length=255, blank=True, verbose_name="Модель телефона")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IN_STOCK,
        verbose_name="Статус",
    )
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    date_added = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    added_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name="Добавил",
        related_name="devices",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def soft_delete(self, user=None):
        """Мягкое удаление устройства"""
        self.status = self.STATUS_TRASH
        self.deleted_at = timezone.now()
        self.save()
        
        # Логируем действие
        if user:
            log_device_history(
                device=self,
                changed_by=user,
                previous_status=self.status,  # Сохраняем предыдущий статус
                new_status=self.STATUS_TRASH,
                previous_comment=self.comment,
                new_comment=self.comment,
            )
    
    def restore(self, user=None):
        """Восстановление устройства из корзины"""
        self.status = self.STATUS_IN_STOCK
        self.deleted_at = None
        self.save()
        
        # Логируем действие
        if user:
            log_device_history(
                device=self,
                changed_by=user,
                previous_status=self.STATUS_TRASH,
                new_status=self.STATUS_IN_STOCK,
                previous_comment=self.comment,
                new_comment=self.comment,
            )
    def days_until_permanent_deletion(self):
        """Возвращает количество дней до полного удаления"""
        if self.status != self.STATUS_TRASH or not self.deleted_at:
            return None
        
        days_in_trash = (timezone.now() - self.deleted_at).days
        days_remaining = 30 - days_in_trash
        return max(0, days_remaining)
    
    def is_near_permanent_deletion(self):
        """Проверяет, скоро ли устройство будет удалено навсегда"""
        days_remaining = self.days_until_permanent_deletion()
        return days_remaining is not None and days_remaining <= 7
            
class DeviceHistory(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="history", verbose_name="Устройство")
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Изменил",
    )
    previous_status = models.CharField(max_length=20, choices=Device.STATUS_CHOICES, verbose_name="Был статус")
    new_status = models.CharField(max_length=20, choices=Device.STATUS_CHOICES, verbose_name="Новый статус")
    previous_comment = models.TextField(blank=True, verbose_name="Был комментарий")
    new_comment = models.TextField(blank=True, verbose_name="Новый комментарий")
    changed_at = models.DateTimeField(default=timezone.now, verbose_name="Когда")

    class Meta:
        ordering = ['-changed_at']
        verbose_name = "История устройства"
        verbose_name_plural = "История устройств"

    def __str__(self):
        return f"{self.device.imei}: {self.previous_status} → {self.new_status}"


class UserProfile(models.Model):
    class Roles(models.TextChoices):
        ADMIN = 'admin', 'Администратор'
        OPERATOR = 'operator', 'Оператор'
        GUEST = 'guest', 'Гость'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.GUEST)
    can_delete_devices = models.BooleanField(
        default=True,
        verbose_name='Можно удалять устройства',
        help_text='Если выключено — оператор может только добавлять устройства.',
    )
    is_super_admin = models.BooleanField(
        default=False,
        verbose_name='Суперадминистратор',
        help_text='Полный доступ ко всем функциям, нельзя понизить.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        role_display = "Суперадмин" if self.is_super_admin else self.get_role_display()
        return f"{self.user.get_username()} ({role_display})"