from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from devices.models import Device

class Command(BaseCommand):
    help = 'Удаляет устройства из корзины старше 30 дней'
    
    def handle(self, *args, **options):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        old_devices = Device.objects.filter(
            status=Device.STATUS_TRASH,
            deleted_at__lt=thirty_days_ago
        )
        
        count = old_devices.count()
        old_devices.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Удалено {count} устройств из корзины старше 30 дней')
        )