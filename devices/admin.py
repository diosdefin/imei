from django.contrib import admin

from .models import Device, DeviceHistory, UserProfile


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('imei', 'model_name', 'status', 'date_added', 'added_by')
    search_fields = ('imei', 'model_name', 'comment')
    list_filter = ('status', 'date_added')
    autocomplete_fields = ('added_by',)


@admin.register(DeviceHistory)
class DeviceHistoryAdmin(admin.ModelAdmin):
    list_display = ('device', 'previous_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status', 'changed_at')
    search_fields = ('device__imei', 'changed_by__username')



@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'can_delete_devices', 'updated_at')
    list_filter = ('role', 'can_delete_devices')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    
    def username(self, obj):
        return obj.user.username
    username.short_description = 'Логин'
    
    def email(self, obj):
        return obj.user.email
    email.short_description = 'Email'