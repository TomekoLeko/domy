"""API urlopów (Vacation) — panel admin + baner dla sklepu."""

import json
from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from domy.decorators import require_authenticated_staff_or_superuser

from .models import Vacation


def _vacation_to_dict(vacation):
    return {
        'id': vacation.id,
        'start_date': vacation.start_date.isoformat() if vacation.start_date else None,
        'end_date': vacation.end_date.isoformat() if vacation.end_date else None,
        'created_at': vacation.created_at.isoformat() if vacation.created_at else None,
    }


def _parse_date(value, field_name):
    if value is None or value == '':
        return None, f'{field_name} is required'
    if isinstance(value, str):
        value = value.strip()
        try:
            from datetime import date

            return date.fromisoformat(value), None
        except ValueError:
            return None, f'{field_name} must be YYYY-MM-DD'
    return None, f'{field_name} must be YYYY-MM-DD'


def _parse_vacation_payload(data):
    start_date, start_err = _parse_date(data.get('start_date'), 'start_date')
    if start_err:
        return None, start_err
    end_date, end_err = _parse_date(data.get('end_date'), 'end_date')
    if end_err:
        return None, end_err
    if end_date < start_date:
        return None, 'Data zakończenia nie może być wcześniejsza niż data rozpoczęcia.'
    return {'start_date': start_date, 'end_date': end_date}, None


def _active_notice_queryset():
    """Urlopy do banera: start <= dziś+7 i end >= dziś (nadchodzące lub trwające)."""
    today = timezone.localdate()
    window_end = today + timedelta(days=7)
    return Vacation.objects.filter(start_date__lte=window_end, end_date__gte=today).order_by('start_date')


@require_GET
@require_authenticated_staff_or_superuser
def api_list_vacations(request):
    vacations = Vacation.objects.all().order_by('start_date')
    return JsonResponse(
        {'vacations': [_vacation_to_dict(v) for v in vacations]},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_add_vacation(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    payload, error = _parse_vacation_payload(data)
    if error:
        return JsonResponse({'detail': error}, status=400)

    vacation = Vacation.objects.create(**payload)
    return JsonResponse(
        {'status': 'success', 'vacation': _vacation_to_dict(vacation)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_edit_vacation(request, vacation_id):
    vacation = get_object_or_404(Vacation, id=vacation_id)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    payload, error = _parse_vacation_payload(data)
    if error:
        return JsonResponse({'detail': error}, status=400)

    vacation.start_date = payload['start_date']
    vacation.end_date = payload['end_date']
    vacation.save()

    return JsonResponse(
        {'status': 'success', 'vacation': _vacation_to_dict(vacation)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_vacation(request, vacation_id):
    vacation = get_object_or_404(Vacation, id=vacation_id)
    vacation.delete()
    return JsonResponse({'status': 'success'})


@require_GET
def api_vacation_notices(request):
    """
    Baner urlopu dla zalogowanych użytkowników (home / koszyk).
    Zwraca urlopy spełniające warunek: start_date <= dziś+7 i end_date >= dziś.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    vacations = _active_notice_queryset()
    return JsonResponse(
        {'vacations': [_vacation_to_dict(v) for v in vacations]},
        json_dumps_params={'ensure_ascii': False},
    )
