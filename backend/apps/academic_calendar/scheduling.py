from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from rest_framework.exceptions import ValidationError


def campus_timezone(campus_id):
    value = getattr(settings, 'CALENDAR_CAMPUS_TIMEZONES', {}).get(str(campus_id))
    if not value:
        raise ValidationError({'timezone': 'Configure an IANA timezone for this campus before converting dates.'})
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError({'timezone': 'The configured campus timezone is invalid.'}) from None


def slot_datetimes(slot, day):
    zone = campus_timezone(slot.campus_id)
    def convert(value):
        naive = datetime.combine(day, value)
        candidates = []
        for fold in (0, 1):
            local = naive.replace(tzinfo=zone, fold=fold)
            if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive:
                candidates.append(local)
        if not candidates or len({x.utcoffset() for x in candidates}) != 1:
            raise ValidationError({'time': 'Local time is nonexistent or ambiguous at a daylight-saving transition.'})
        return candidates[0]
    return convert(slot.start_time), convert(slot.end_time)
