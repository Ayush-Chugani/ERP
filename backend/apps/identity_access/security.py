"""Account security services. Integration is enabled separately from installation."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from .evaluator import usable
from .models import LoginAudit, PasswordHistory
from .audit import record


def verify_factor(user, proof, purpose):
    provider = getattr(settings, 'IDENTITY_ACCESS_MFA_PROVIDER', '')
    if not provider:
        return False
    # Provider must atomically consume/replay-protect proofs and bind purpose/user.
    return import_string(provider)(user=user, proof=proof, purpose=purpose) is True


def step_up(user, proof):
    if not isinstance(proof, dict) or not user.check_password(proof.get('password', '')):
        raise PermissionDenied('Additional authentication required.')
    if user.multi_factor_enabled and not verify_factor(user, proof.get('mfa'), 'step_up'):
        raise PermissionDenied('Additional authentication required.')


def login(*, username, password, mfa=None, ip=None, user_agent=None):
    now = timezone.now()
    successful = False
    session_id = uuid.uuid4().hex
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().filter(username=username).first()
        valid_password = user.check_password(password) if user else False
        if user is None:
            make_password(password)  # Missing accounts still incur password-hasher work.
        eligible = usable(user, now) if user else False
        successful = eligible and valid_password
        if successful and user.multi_factor_enabled:
            successful = verify_factor(user, mfa, 'login')
        if user:
            if successful:
                user.failed_login_count = 0
                user.locked_until = None
                user.last_login_at = now
                user.last_login = now
            elif eligible:
                user.failed_login_count = min(user.failed_login_count + 1, 65535)
                if user.failed_login_count >= settings.IDENTITY_ACCESS_LOGIN_LIMIT:
                    user.locked_until = now + timedelta(seconds=settings.IDENTITY_ACCESS_LOCK_SECONDS)
            user.save(update_fields=['failed_login_count','locked_until','last_login_at','last_login','updated_at'])
        LoginAudit.objects.create(user=user, username_attempted=username[:100], ip_address=ip,
            user_agent=(user_agent or '')[:500], was_successful=successful,
            failure_reason=None if successful else 'Authentication rejected', session_identifier=session_id)
    # Raise after commit so lockout counters and failed-login evidence survive.
    if not successful:
        raise AuthenticationFailed('Invalid username or password.')
    return user, session_id


def token_claims(user, token, session_id):
    token['security_version'] = user.security_version
    token['password_stamp'] = user.get_session_auth_hash()
    token['mfa_verified'] = bool(user.multi_factor_enabled)
    token['session_id'] = session_id


def validate_session(user, token):
    if (not usable(user, timezone.now()) or token.get('security_version') != user.security_version
        or not isinstance(token.get('password_stamp'),str)
        or not constant_time_compare(token['password_stamp'],user.get_session_auth_hash())):
        raise AuthenticationFailed('Authentication required.')
    if user.multi_factor_enabled and token.get('mfa_verified') is not True:
        raise AuthenticationFailed('Authentication required.')


@transaction.atomic
def change_password(*, actor, current_password, new_password, mfa=None):
    user = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not usable(user, timezone.now()) or not user.check_password(current_password):
        raise PermissionDenied('Authentication required.')
    if user.multi_factor_enabled and not verify_factor(user, mfa, 'password_change'):
        raise PermissionDenied('Additional authentication required.')
    _replace_password(user, new_password)
    return user


def _replace_password(user, password):
    validate_password(password, user)
    hashes = list(PasswordHistory.objects.filter(user=user).order_by('-changed_at','-pk')
                  .values_list('password_hash',flat=True)[:settings.IDENTITY_ACCESS_PASSWORD_HISTORY])
    if any(check_password(password, encoded) for encoded in [user.password, *hashes]):
        raise ValidationError('Choose a password that has not been used recently.')
    PasswordHistory.objects.create(user=user, password_hash=user.password)
    user.set_password(password)
    user.password_changed_at=timezone.now()
    user.must_change_password=False
    user.security_version+=1
    user.save(update_fields=['password','password_changed_at','must_change_password','security_version','updated_at'])
    record(actor=user,action='UPDATE',entity=user,details={'event':'password_changed'})


@transaction.atomic
def reset_password(*, user_id, token, new_password, mfa=None):
    user = get_user_model().objects.select_for_update().filter(pk=user_id).first()
    if not user or not user.is_active or user.account_status != 'ACTIVE' or not default_token_generator.check_token(user, token):
        raise PermissionDenied('Reset unavailable.')
    if user.multi_factor_enabled and not verify_factor(user, mfa, 'password_reset'):
        raise PermissionDenied('Reset unavailable.')
    _replace_password(user, new_password)
    user.failed_login_count=0; user.locked_until=None
    user.save(update_fields=['failed_login_count','locked_until'])


@transaction.atomic
def configure_mfa(*, actor, enabled, proof):
    user = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not usable(user,timezone.now()):
        raise PermissionDenied()
    step_up(user,proof)
    if enabled and not verify_factor(user,proof.get('enrollment'),'enroll'):
        raise PermissionDenied('Verified MFA enrollment required.')
    user.multi_factor_enabled=enabled
    user.security_version+=1
    user.save(update_fields=['multi_factor_enabled','security_version','updated_at'])
    record(actor=user,action='CONFIGURE',entity=user,details={'event':'mfa_changed','enabled':enabled})


@transaction.atomic
def logout_session(*,actor,session_id):
    if actor is None or not session_id:
        return
    # The only permitted audit completion update; original login evidence remains.
    LoginAudit._base_manager.filter(user=actor,session_identifier=session_id,
        was_successful=True,logout_at__isnull=True).update(logout_at=timezone.now())
    record(actor=actor,action='UPDATE',details={'event':'logout','session_id':session_id})
