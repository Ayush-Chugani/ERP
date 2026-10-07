"""Explicit, authenticated account invitations; never infer links from email."""

import hashlib, secrets
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from . import models as m
from .permissions import scoped, institution_id, enabled
from .services import stable_errors, lock_actor, audit
from .integrations.upstream import Membership


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@stable_errors
def invite(*, actor, model, pk, user_id, reason):
    if model not in (m.Student, m.Employee) or not reason.strip() or len(reason) > 250:
        raise ValidationError("Person and bounded reason required.")
    with transaction.atomic():
        actor = lock_actor(actor)
        if not actor.has_perm("people_master.manage_accountlink"):
            raise PermissionDenied()
        person = (
            scoped(model, actor, "change").select_for_update().filter(pk=pk).first()
        )
        if person is None:
            raise NotFound()
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if (
            not user
            or not Membership.objects.filter(
                user=user, institution_id=person.institution_id, is_active=True
            ).exists()
        ):
            raise ValidationError(
                "Account requires an active membership in the same institution."
            )
        token = secrets.token_urlsafe(32)
        field = "student" if model is m.Student else "employee"
        invitation = m.AccountInvitation.objects.create(
            **{field: person},
            intended_user=user,
            created_by=actor,
            token_hash=digest(token),
            expires_at=timezone.now() + timedelta(hours=24),
        )
        audit(person, actor, "account_invited", {}, reason)
        # Returned once to the authorized operator; caller arranges delivery.
        return {
            "token": token,
            "expires_at": invitation.expires_at,
            "id": str(invitation.pk),
        }


@stable_errors
def accept(*, actor, token):
    with transaction.atomic():
        actor = lock_actor(actor)
        invitation = (
            m.AccountInvitation.objects.select_for_update()
            .filter(
                token_hash=digest(token),
                intended_user=actor,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not invitation:
            raise NotFound("Invitation unavailable.")
        person = invitation.student or invitation.employee
        if not Membership.objects.filter(
            user=actor,
            institution_id=person.institution_id,
            is_active=True,
            institution__is_active=True,
            institution__institutionmodule__people_master=True,
        ).exists():
            raise PermissionDenied()
        name = "student" if invitation.student_id else "employee"
        link = m.AccountLink.objects.create(user=actor, **{name: person})
        invitation.used_at = timezone.now()
        invitation.save(update_fields=["used_at"])
        audit(person, actor, "account_linked", {}, "Verified invitation accepted")
        return {"id": str(link.pk)}


@stable_errors
def unlink(*, actor, model, pk, reason):
    if model not in (m.Student, m.Employee) or not reason.strip() or len(reason) > 250:
        raise ValidationError("Person and bounded reason required.")
    with transaction.atomic():
        actor = lock_actor(actor)
        if not actor.has_perm("people_master.manage_accountlink"):
            raise PermissionDenied()
        person = scoped(model, actor, "change").filter(pk=pk).first()
        if not person:
            raise NotFound()
        name = "student" if model is m.Student else "employee"
        m.AccountLink.objects.filter(**{name: person}).delete()
        m.AccountInvitation.objects.filter(
            **{name: person}, used_at__isnull=True
        ).update(used_at=timezone.now())
        audit(person, actor, "account_unlinked", {}, reason)
        return {"unlinked": True}


@stable_errors
def provision(*, actor, model, pk, username, email, reason):
    """Create an inactive account with no password or roles; invitation proves control."""
    from django.core.validators import validate_email

    if not reason.strip() or len(reason) > 250:
        raise ValidationError("A bounded reason is required.")
    validate_email(email)
    with transaction.atomic():
        actor = lock_actor(actor)
        if not actor.has_perm("accounts.manage_platform_access") or not actor.has_perm(
            "people_master.manage_accountlink"
        ):
            raise PermissionDenied()
        person = scoped(model, actor, "change").filter(pk=pk).first()
        if person is None:
            raise NotFound()
        User = get_user_model()
        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=username).exists()
        ):
            raise ValidationError(
                "An account with these identifiers already exists; use explicit linking."
            )
        user = User(username=username, email=email, is_active=False)
        user.set_unusable_password()
        user.full_clean()
        user.save()
        Membership.objects.create(
            user=user, institution_id=person.institution_id, is_active=True
        )
        token = secrets.token_urlsafe(32)
        name = "student" if model is m.Student else "employee"
        invitation = m.AccountInvitation.objects.create(
            **{name: person},
            intended_user=user,
            created_by=actor,
            token_hash=digest(token),
            expires_at=timezone.now() + timedelta(hours=24),
        )
        audit(person, actor, "account_provisioned", {}, reason)
        return {
            "token": token,
            "user_id": str(user.pk),
            "expires_at": invitation.expires_at,
        }


@stable_errors
def claim(*, token, password):
    from django.conf import settings
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.password_validation import validate_password

    if not getattr(settings, "PEOPLE_MASTER_ENABLED", False):
        raise PermissionDenied()
    with transaction.atomic():
        ContentType.objects.select_for_update().get(
            app_label="organization", model="university"
        )
        invitation = (
            m.AccountInvitation.objects.select_for_update()
            .select_related("intended_user")
            .filter(
                token_hash=digest(token),
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not invitation:
            raise NotFound("Invitation unavailable.")
        user = invitation.intended_user
        if user.is_active or user.has_usable_password():
            raise NotFound("Use authenticated acceptance for an existing account.")
        validate_password(password, user)
        user.set_password(password)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])
        return accept(actor=user, token=token)


@stable_errors
def manage_account(*, actor, model, pk, active=None, email=None, reason):
    """Platform-only global account change; never conflated with domain status."""
    from django.core.validators import validate_email

    if not reason.strip() or len(reason) > 250:
        raise ValidationError("A bounded reason is required.")
    with transaction.atomic():
        actor = lock_actor(actor)
        if not actor.is_superuser:
            raise PermissionDenied()
        person = scoped(model, actor, "change").filter(pk=pk).first()
        if person is None:
            raise NotFound()
        name = "student" if model is m.Student else "employee"
        link = (
            m.AccountLink.objects.select_related("user")
            .filter(**{name: person})
            .first()
        )
        if not link:
            raise NotFound("No linked account.")
        user = link.user
        if user.is_superuser or user.pk == actor.pk:
            raise ValidationError(
                "Manage privileged accounts in the platform account workflow."
            )
        if active is not None:
            if type(active) is not bool:
                raise ValidationError("active must be boolean.")
            user.is_active = active
        if email is not None:
            validate_email(email)
            if (
                get_user_model()
                .objects.filter(email__iexact=email)
                .exclude(pk=user.pk)
                .exists()
            ):
                raise ValidationError("Email already in use.")
            user.email = email
        user.full_clean()
        user.save()
        audit(person, actor, "account_updated", {}, reason)
        return {"user_id": str(user.pk), "is_active": user.is_active}
