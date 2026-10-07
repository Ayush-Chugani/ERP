"""Pure calculation primitives: no institutional defaults or mutable status lookups."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def decimal(value, name):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{name} must be a finite decimal.') from None
    if not result.is_finite():
        raise ValueError(f'{name} must be a finite decimal.')
    return result


def validate_rules(rules):
    if not isinstance(rules, dict) or not rules:
        raise ValueError('Supply explicit status rules.')
    for code, rule in rules.items():
        if not isinstance(code, str) or not code or not isinstance(rule, dict) or set(rule) != {'credit', 'denominator'}:
            raise ValueError('Each status needs credit and denominator weights.')
        credit = decimal(rule['credit'], 'credit')
        denominator = decimal(rule['denominator'], 'denominator')
        if not Decimal(0) <= credit <= denominator <= Decimal(1):
            raise ValueError('Require 0 <= credit <= denominator <= 1.')
    return rules


def contribution(*, rule, basis, duration_minutes):
    validate_rules({'status': rule})
    duration = decimal(duration_minutes, 'duration_minutes')
    if duration <= 0 or basis not in ('SESSION', 'DURATION'):
        raise ValueError('Positive duration and SESSION or DURATION basis required.')
    units = Decimal(1) if basis == 'SESSION' else duration
    return units * decimal(rule['credit'], 'credit'), units * decimal(rule['denominator'], 'denominator')


def summarize(rows, threshold):
    """Rows are immutable finalized contributions from one policy version/basis."""
    threshold = decimal(threshold, 'threshold')
    if not 0 <= threshold <= 100:
        raise ValueError('Threshold must be between 0 and 100.')
    earned = Decimal(0)
    possible = Decimal(0)
    for row in rows:
        credit = decimal(row['credit'], 'credit')
        denominator = decimal(row['denominator'], 'denominator')
        if not 0 <= credit <= denominator:
            raise ValueError('Invalid stored contribution.')
        earned += credit
        possible += denominator
    percentage = earned * 100 / possible if possible else None
    return {
        'credit': str(earned), 'denominator': str(possible),
        'percentage': str(percentage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if percentage is not None else None,
        # Compare exact totals, not the rounded percentage.
        'shortage': earned * 100 < possible * threshold if possible else None,
        'threshold': str(threshold),
    }
