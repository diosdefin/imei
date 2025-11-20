import json
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from .models import Device, DeviceHistory
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .utils import can_delete_devices, is_admin, is_guest, is_operator, log_device_history, get_user_profile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
    
)
from .utils import (
    can_delete_devices, 
    is_admin, 
    is_guest, 
    is_operator, 
    log_device_history, 
    get_user_profile,
    is_super_admin,
    is_admin_or_super
)
from .forms import DeviceFilterForm, DeviceForm, DeviceStatusForm, UserProfileForm
from .models import Device, UserProfile
from .services import (
    ImeiLookupError,
    ImeiLookupRateLimitError,
    apply_device_filters,
    lookup_device_by_imei,
)
from .utils import can_delete_devices, is_admin, is_guest, is_operator, log_device_history
from django.contrib.auth import login
from .forms import UserRegistrationForm

class RegisterView(View):
    template_name = 'registration/register.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = UserRegistrationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
            
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Получаем профиль, который уже создан сигналом, и обновляем его
            try:
                profile = user.profile
                # Обновляем роль на гостя (вместо дефолтной)
                profile.role = UserProfile.Roles.GUEST
                profile.can_delete_devices = False
                profile.save()
            except UserProfile.DoesNotExist:
                # На всякий случай, если профиль не создался
                UserProfile.objects.create(
                    user=user,
                    role=UserProfile.Roles.GUEST,
                    can_delete_devices=False
                )
            
            # Автоматически входим пользователя после регистрации
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать!')
            return redirect('dashboard')
        
        return render(request, self.template_name, {'form': form})
    
@require_POST
def add_device_from_scan(request):
    if not request.user.is_authenticated or not is_operator(request.user):
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'}, status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных'}, status=400)

    imei = (payload.get('imei') or '').strip()
    model_name = (payload.get('model_name') or '').strip()
    status = payload.get('status') or Device.STATUS_IN_STOCK
    comment = (payload.get('comment') or '').strip()

    if not imei:
        return JsonResponse({'success': False, 'error': 'IMEI не предоставлен'}, status=400)

    if len(imei) != 15 or not imei.isdigit():
        return JsonResponse({'success': False, 'error': 'IMEI должен содержать 15 цифр'}, status=400)

    if Device.objects.filter(imei=imei).exists():
        return JsonResponse({'success': False, 'error': 'Устройство с таким IMEI уже существует'}, status=400)

    if status not in dict(Device.PUBLIC_STATUS_CHOICES):
        status = Device.STATUS_IN_STOCK

    if not model_name:
        try:
            lookup = lookup_device_by_imei(imei)
            model_name = lookup.formatted_name
        except ImeiLookupRateLimitError as exc:
            return JsonResponse({'success': False, 'error': str(exc), 'rate_limited': True}, status=429)
        except ImeiLookupError:
            model_name = ''

    device = Device.objects.create(
        imei=imei,
        model_name=model_name,
        status=status,
        comment=comment,
        added_by=request.user,
    )

    return JsonResponse(
        {
            'success': True,
            'device_id': device.id,
            'model_name': device.model_name,
            'status': device.get_status_display(),
        }
    )


class GuestRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_guest(self.request.user)


class OperatorRequiredMixin(GuestRequiredMixin):
    def test_func(self):
        return is_operator(self.request.user)


class AdminRequiredMixin(GuestRequiredMixin):
    def test_func(self):
        return is_admin(self.request.user)


class DeletionPermissionMixin(OperatorRequiredMixin):
    def test_func(self):
        return can_delete_devices(self.request.user)


class DashboardView(GuestRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_devices'] = Device.objects.count()
        context['trash_count'] = Device.objects.filter(status=Device.STATUS_TRASH).count()
        context['sold_count'] = Device.objects.filter(status=Device.STATUS_SOLD).count()
        context['written_off_count'] = Device.objects.filter(status=Device.STATUS_WRITTEN_OFF).count()

        recent_qs = Device.objects.select_related('added_by')
        paginator = Paginator(recent_qs, settings.RECENT_DEVICE_PAGE_SIZE)
        page_number = self.request.GET.get('recent_page') or 1
        recent_page = paginator.get_page(page_number)
        context['recent_devices'] = recent_page
        context['recent_paginator'] = paginator
        context['recent_page_number'] = recent_page.number
        context['is_admin'] = is_admin(self.request.user)
        return context


class DeviceListView(GuestRequiredMixin, ListView):
    model = Device
    template_name = 'devices/device_list.html'
    context_object_name = 'devices'
    paginate_by = getattr(settings, 'DEVICE_LIST_PAGE_SIZE', 20)
    
    def get_queryset(self):
        # ВАЖНО: Исключаем устройства в корзине
        queryset = Device.objects.exclude(status='trash').select_related('added_by')
        
        # Поиск
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(imei__icontains=search) |
                Q(model_name__icontains=search) |
                Q(comment__icontains(search))
            )
        
        # Фильтр по статусу
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        # Фильтр по пользователю
        user_id = self.request.GET.get('user', '')
        if user_id:
            queryset = queryset.filter(added_by_id=user_id)
        
        # Фильтр по дате
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(date_added__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(date_added__lte=date_to)
            except ValueError:
                pass
        
        # Сортировка
        sort = self.request.GET.get('sort', 'date_desc')
        if sort == 'imei':
            queryset = queryset.order_by('imei')
        elif sort == 'model':
            queryset = queryset.order_by('model_name')
        elif sort == 'status':
            queryset = queryset.order_by('status')
        elif sort == 'date_asc':
            queryset = queryset.order_by('date_added')
        else:
            queryset = queryset.order_by('-date_added')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Статусы для фильтра (исключаем trash)
        context['statuses'] = [
            (key, label) for key, label in Device.STATUS_CHOICES 
            if key != 'trash'
        ]
        
        # Упорядоченный список пользователей с логинами
        context['users'] = User.objects.order_by('username')
        
        # Сохраняем параметры фильтра для пагинации
        querystring = self.request.GET.copy()
        if 'page' in querystring:
            del querystring['page']
        context['querystring'] = querystring.urlencode()
        
        # Информация о фильтрах
        context['active_filters'] = bool(self.request.GET)
        context['devices_count'] = context['paginator'].count if hasattr(context, 'paginator') else context['devices'].count()
        
        # Права доступа
        context['is_manager'] = is_admin(self.request.user)
        context['is_operator'] = is_operator(self.request.user)
        context['can_delete'] = can_delete_devices(self.request.user)
        
        # Статистика по корзине
        context['trash_count'] = Device.objects.filter(status='trash').count()
        
        return context
    
class DeviceCreateView(OperatorRequiredMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = 'devices/device_form.html'
    success_url = reverse_lazy('device_list')

    def get_initial(self):
        initial = super().get_initial()
        if imei := self.request.GET.get('imei'):
            initial['imei'] = imei
        return initial

    def form_valid(self, form):
        form.instance.added_by = self.request.user
        if not form.instance.model_name:
            try:
                lookup = lookup_device_by_imei(form.instance.imei)
                form.instance.model_name = lookup.formatted_name
            except ImeiLookupRateLimitError as exc:
                messages.warning(self.request, f'Лимит IMEICheck: {exc}')
            except ImeiLookupError as exc:
                messages.warning(self.request, f'Автозаполнение не удалось: {exc}')
        response = super().form_valid(form)
        messages.success(self.request, 'Устройство успешно добавлено.')
        return response


class DeviceUpdateView(AdminRequiredMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = 'devices/device_form.html'
    success_url = reverse_lazy('device_list')

    def form_valid(self, form):
        device = form.instance
        previous_status = device.status
        previous_comment = device.comment
        response = super().form_valid(form)
        log_device_history(
            device=device,
            changed_by=self.request.user,
            previous_status=previous_status,
            new_status=device.status,
            previous_comment=previous_comment,
            new_comment=device.comment,
        )
        messages.success(self.request, 'Изменения сохранены.')
        return response


class DeviceDeleteView(DeletionPermissionMixin, DeleteView):
    model = Device
    template_name = 'devices/device_confirm_delete.html'
    success_url = reverse_lazy('device_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Мягкое удаление вместо полного
        self.object.soft_delete(user=request.user)
        
        messages.success(request, 'Устройство перемещено в корзину.')
        return redirect(self.get_success_url())


class ScanView(OperatorRequiredMixin, TemplateView):
    template_name = 'devices/scan.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = Device.PUBLIC_STATUS_CHOICES
        context['default_status'] = Device.STATUS_IN_STOCK
        return context


class DeviceStatusUpdateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        form = DeviceStatusForm(request.POST, instance=device)
        if form.is_valid():
            previous_status = device.status
            form.save()
            log_device_history(
                device=device,
                changed_by=request.user,
                previous_status=previous_status,
                new_status=device.status,
                previous_comment=device.comment,
                new_comment=device.comment,
            )
            return JsonResponse(
                {'success': True, 'status': device.status, 'status_label': device.get_status_display()}
            )
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ExportDevicesView(AdminRequiredMixin, View):
    def get(self, request):
        from openpyxl import Workbook

        # ТОЧНО ТАК ЖЕ КАК В DeviceListView
        queryset = Device.objects.exclude(status='trash').select_related('added_by')
        
        # Применяем все фильтры
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(imei__icontains=search) |
                Q(model_name__icontains=search) |
                Q(comment__icontains=search)
            )
        
        status = request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        user_id = request.GET.get('user', '')
        if user_id:
            queryset = queryset.filter(added_by_id=user_id)
        
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(date_added__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(date_added__lte=date_to)
            except ValueError:
                pass

        # Сортировка
        sort = request.GET.get('sort', 'date_desc')
        if sort == 'imei':
            queryset = queryset.order_by('imei')
        elif sort == 'model':
            queryset = queryset.order_by('model_name')
        elif sort == 'status':
            queryset = queryset.order_by('status')
        elif sort == 'date_asc':
            queryset = queryset.order_by('date_added')
        else:
            queryset = queryset.order_by('-date_added')

        wb = Workbook()
        ws = wb.active
        ws.title = 'Устройства'
        
        # Заголовки
        ws.append(['IMEI', 'Модель', 'Статус', 'Комментарий', 'Добавлено', 'Добавил'])
        
        for device in queryset:
            ws.append([
                device.imei,
                device.model_name or '',
                device.get_status_display(),
                device.comment or '',
                timezone.localtime(device.date_added).strftime('%d.%m.%Y %H:%M'),
                device.added_by.get_full_name() or device.added_by.username,
            ])
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="devices.xlsx"'
        wb.save(response)
        return response
    
class DeviceHistoryView(GuestRequiredMixin, TemplateView):
    template_name = 'devices/device_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device = get_object_or_404(Device, pk=self.kwargs['pk'])
        context['device'] = device
        context['history'] = device.history.select_related('changed_by')
        return context


class DeviceRestoreView(AdminRequiredMixin, View):
    def post(self, request, pk):
        device = get_object_or_404(Device, pk=pk, status='trash')
        
        # Восстанавливаем устройство
        device.status = 'in_stock'  # Возвращаем в "В наличии"
        device.deleted_at = None    # Очищаем время удаления
        device.save()
        
        # Логируем восстановление
        log_device_history(
            device=device,
            changed_by=request.user,
            previous_status='trash',
            new_status='in_stock',
            previous_comment=device.comment,
            new_comment=device.comment,
        )
        
        messages.success(request, f'Устройство {device.imei} восстановлено из корзины.')
        return redirect('device_trash')
    
class ImeiLookupView(OperatorRequiredMixin, View):
    def get(self, request):
        imei = (request.GET.get('imei') or '').strip()
        force_refresh = request.GET.get('refresh') == '1'
        if not imei:
            return JsonResponse({'success': False, 'error': 'IMEI обязателен'}, status=400)
        try:
            lookup = lookup_device_by_imei(imei, force_refresh=force_refresh)
        except ImeiLookupRateLimitError as exc:
            return JsonResponse({'success': False, 'error': str(exc), 'rate_limited': True}, status=429)
        except ImeiLookupError as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)

        return JsonResponse(
            {
                'success': True,
                'imei': lookup.imei,
                'brand': lookup.brand,
                'model': lookup.model,
                'model_name': lookup.model_name,
                'formatted_name': lookup.formatted_name,
            }
        )


class AdminPanelView(AdminRequiredMixin, TemplateView):
    template_name = 'admin_panel.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profiles = UserProfile.objects.select_related('user').order_by('user__username')
        forms = []
        for profile in profiles:
            prefix = f'profile-{profile.pk}'
            forms.append(
                {
                    'instance': profile,
                    'form': UserProfileForm(instance=profile, prefix=prefix),
                }
            )
        context['profiles'] = forms
        context['total_users'] = profiles.count()
        return context

    def post(self, request, *args, **kwargs):
        profile_id = request.POST.get('profile_id')
        profile = get_object_or_404(UserProfile, pk=profile_id)
        prefix = f'profile-{profile.pk}'
        form = UserProfileForm(request.POST, instance=profile, prefix=prefix)
        if form.is_valid():
            new_role = form.cleaned_data['role']
            if profile.user == request.user and new_role != UserProfile.Roles.ADMIN:
                messages.error(request, 'Нельзя снять с себя роль администратора.')
            else:
                form.save()
                messages.success(request, f'Права пользователя {profile.user.username} обновлены.')
        else:
            messages.error(request, 'Не удалось обновить профиль пользователя.')
        return redirect('admin_panel')
    
class DeviceSoftDeleteView(DeletionPermissionMixin, UpdateView):
    model = Device
    template_name = 'devices/device_confirm_delete.html'  # Используем существующий шаблон
    fields = []
    success_url = reverse_lazy('device_list')
    
    def form_valid(self, form):
        device = form.save(commit=False)
        print(f"=== DEBUG SOFT DELETE ===")
        print(f"До удаления: статус={device.status}, deleted_at={device.deleted_at}")
        
        previous_status = device.status
        device.status = 'trash'  # Явно указываем строку
        device.deleted_at = timezone.now()
        device.save()
        
        print(f"После удаления: статус={device.status}, deleted_at={device.deleted_at}")
        print("=== END DEBUG ===")
        
        # Проверяем, что устройство действительно в корзине
        device.refresh_from_db()
        print(f"Проверка после save: статус={device.status}")
        
        # Логируем изменение статуса
        log_device_history(
            device=device,
            changed_by=self.request.user,
            previous_status=previous_status,
            new_status=device.status,
            previous_comment=device.comment,
            new_comment=device.comment,
        )
        
        messages.success(self.request, f'Устройство {device.imei} перемещено в корзину. Оно будет храниться там 30 дней.')
        return redirect(self.get_success_url())
    
# Добавляем URL для ручного добавления устройства
class DeviceAddManualView(OperatorRequiredMixin, View):
    def post(self, request):
        imei = request.POST.get('imei', '').strip()
        
        if not imei:
            messages.error(request, 'IMEI не может быть пустым')
            return redirect('scan')
        
        if len(imei) != 15 or not imei.isdigit():
            messages.error(request, 'IMEI должен содержать ровно 15 цифр')
            return redirect('scan')
        
        if Device.objects.filter(imei=imei).exists():
            messages.error(request, 'Устройство с таким IMEI уже существует')
            return redirect('scan')
        
        # Создаем устройство
        device = Device.objects.create(
            imei=imei,
            model_name='',  # Можно добавить автоматическое определение
            status=Device.STATUS_IN_STOCK,
            added_by=request.user
        )
        
        messages.success(request, f'Устройство с IMEI {imei} успешно добавлено')
        return redirect('device_list')
    

# Добавляем эти классы в конец views.py (после существующих классов)


class DeviceAddManualView(OperatorRequiredMixin, View):
    def post(self, request):
        imei = request.POST.get('imei', '').strip()
        
        if not imei:
            messages.error(request, 'IMEI не может быть пустым')
            return redirect('scan')
        
        if len(imei) != 15 or not imei.isdigit():
            messages.error(request, 'IMEI должен содержать ровно 15 цифр')
            return redirect('scan')
        
        if Device.objects.filter(imei=imei).exists():
            messages.error(request, 'Устройство с таким IMEI уже существует')
            return redirect('scan')
        
        # Пытаемся определить модель по IMEI
        model_name = ''
        try:
            lookup = lookup_device_by_imei(imei)
            model_name = lookup.formatted_name
        except (ImeiLookupError, ImeiLookupRateLimitError):
            # Если не удалось определить модель, оставляем пустым
            pass
        
        # Создаем устройство
        device = Device.objects.create(
            imei=imei,
            model_name=model_name,
            status=Device.STATUS_IN_STOCK,
            added_by=request.user
        )
        
        messages.success(request, f'Устройство с IMEI {imei} успешно добавлено')
        return redirect('device_list')  
     
class UserManagementView(AdminRequiredMixin, TemplateView):
    template_name = 'devices/user_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = User.objects.all().select_related('profile')
        context['users'] = users
        context['is_super_admin'] = is_super_admin(self.request.user)
        return context
    
    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')
        can_delete = request.POST.get('can_delete') == 'on'
        
        user = get_object_or_404(User, id=user_id)
        current_user = request.user
        
        # Используем get_user_profile из utils
        profile = get_user_profile(user)
        
        # Проверяем права текущего пользователя
        if not is_super_admin(current_user):
            # Обычный админ не может управлять суперадминами
            if profile.is_super_admin:
                messages.error(request, 'Нельзя изменять права суперадминистратора.')
                return redirect('user_management')
            
            # Обычный админ не может назначать/снимать админские права
            if new_role == UserProfile.Roles.ADMIN or profile.role == UserProfile.Roles.ADMIN:
                messages.error(request, 'Только суперадминистратор может управлять администраторами.')
                return redirect('user_management')
        
        # Суперадмин не может понизить себя
        if user == current_user and profile.is_super_admin and new_role != UserProfile.Roles.ADMIN:
            messages.error(request, 'Суперадминистратор не может понизить себя.')
            return redirect('user_management')
        
        # Обновляем права
        if is_super_admin(current_user):
            # Только суперадмин может назначать админов
            profile.role = new_role
        
        if new_role == UserProfile.Roles.OPERATOR:
            profile.can_delete_devices = can_delete
        elif new_role == UserProfile.Roles.GUEST:
            profile.can_delete_devices = False
        
        profile.save()
        messages.success(request, f'Права пользователя {user.username} обновлены.')
        
        return redirect('user_management')

@login_required
def device_trash(request):
    """Отдельная страница для просмотра корзины"""
    # Получаем ТОЛЬКО устройства в корзине
    devices = Device.objects.filter(status='trash').order_by('-deleted_at')
    
    # Добавляем информацию о времени до удаления для каждого устройства
    devices_with_days = []
    urgent_count = 0
    
    for device in devices:
        days_remaining = device.days_until_permanent_deletion()
        is_urgent = days_remaining is not None and days_remaining <= 7
        
        if is_urgent:
            urgent_count += 1
            
        devices_with_days.append({
            'device': device,
            'days_remaining': days_remaining,
            'is_urgent': is_urgent
        })
    
    context = {
        'devices_with_info': devices_with_days,
        'devices_count': devices.count(),
        'urgent_count': urgent_count,  # Добавляем счетчик срочных устройств
        'is_manager': is_admin(request.user),
        'is_operator': is_operator(request.user),
    }
    
    return render(request, 'devices/device_trash.html', context)