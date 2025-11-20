from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, Mapping

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Device

logger = logging.getLogger(__name__)


class ImeiLookupError(Exception):
    """Base exception for IMEI lookup issues."""


class ImeiLookupRateLimitError(ImeiLookupError):
    """Raised when the external API rate limit is reached."""


@dataclass(frozen=True)
class ImeiLookupResult:
    imei: str
    brand: str
    model: str
    model_name: str
    formatted_name: str
    raw_payload: Dict


def _normalized_imei(imei: str) -> str:
    return ''.join(ch for ch in imei if ch.isdigit())


def _cache_key_for_imei(imei: str) -> str:
    return f'imeicheck:payload:{imei}'


def _rate_limit_key() -> str:
    now = timezone.now()
    return f'imeicheck:rate:{now.strftime("%Y%m%d%H%M")}'


def _hit_rate_limit() -> bool:
    """Returns True when the minute rate limit has been exceeded."""
    limit = getattr(settings, 'IMEICHECK_RATE_LIMIT', 30)
    window = getattr(settings, 'IMEICHECK_RATE_WINDOW', 60)
    cache_key = _rate_limit_key()
    added = cache.add(cache_key, 1, timeout=window)
    if added:
        return False
    try:
        current = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=window)
        return False
    return current > limit


def lookup_device_by_imei(imei: str, force_refresh: bool = False) -> ImeiLookupResult:
    """Fetch device details from IMEICheck API."""
    normalized = _normalized_imei(imei)
    if len(normalized) != 15:
        raise ImeiLookupError('IMEI должен содержать 15 цифр.')

    cache_key = _cache_key_for_imei(normalized)
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached:
            return ImeiLookupResult(**cached)

    if _hit_rate_limit():
        raise ImeiLookupRateLimitError('Достигнут лимит внешнего API. Повторите попытку через минуту.')

    params = {
        'key': settings.IMEICHECK_API_KEY,
        'imei': normalized,
        'format': 'json',
    }

    try:
        response = requests.get(
            settings.IMEICHECK_API_URL,
            params=params,
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.exception('Ошибка сети при обращении к IMEICheck: %s', exc)
        raise ImeiLookupError('Не удалось подключиться к сервису IMEICheck.')

    if response.status_code != 200:
        logger.error('IMEICheck ответил статусом %s для IMEI %s', response.status_code, normalized)
        raise ImeiLookupError('Сервис IMEICheck временно недоступен.')

    try:
        payload = response.json()
    except ValueError as exc:
        logger.exception('Не удалось преобразовать ответ IMEICheck в JSON: %s', exc)
        raise ImeiLookupError('IMEICheck вернул некорректный ответ.')

    if payload.get('status') != 'succes':
        logger.warning('IMEICheck вернул ошибку: %s', payload)
        raise ImeiLookupError('IMEI не найден или сервис вернул ошибку.')

    obj = payload.get('object') or {}
    brand = obj.get('brand') or 'Неизвестный бренд'
    model = obj.get('name') or obj.get('model') or 'Неизвестная модель'
    model_code = obj.get('model') or ''

    formatted_name = f'({brand}) - {model}'.strip()

    result_dict = {
        'imei': normalized,
        'brand': brand,
        'model': model_code,
        'model_name': model,
        'formatted_name': formatted_name,
        'raw_payload': payload,
    }

    cache.set(cache_key, result_dict, timeout=24 * 60 * 60)  # Cache for 1 day
    return ImeiLookupResult(**result_dict)


def apply_device_filters(queryset: QuerySet, params: Mapping[str, str]) -> QuerySet:
    """Apply filtering by search, status, date range, and author."""
    search = (params.get('search') or '').strip()
    status = (params.get('status') or '').strip()
    added_by = (params.get('added_by') or '').strip()
    date_from_raw = (params.get('date_from') or '').strip()
    date_to_raw = (params.get('date_to') or '').strip()

    if search:
        queryset = queryset.filter(
            Q(imei__icontains=search)
            | Q(model_name__icontains=search)
            | Q(comment__icontains=search)
        )

    if status:
        queryset = queryset.filter(status=status)

    if added_by:
        queryset = queryset.filter(added_by__id=added_by)

    if date_from_raw:
        date_from = parse_date(date_from_raw)
        if date_from:
            start_dt = timezone.make_aware(datetime.combine(date_from, time.min))
            queryset = queryset.filter(date_added__gte=start_dt)

    if date_to_raw:
        date_to = parse_date(date_to_raw)
        if date_to:
            end_dt = timezone.make_aware(datetime.combine(date_to, time.max))
            queryset = queryset.filter(date_added__lte=end_dt)

    return queryset

