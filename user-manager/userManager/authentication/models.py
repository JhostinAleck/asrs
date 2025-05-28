from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    Extended User model with security tracking
    """
    # redefinimos los M2M para evitar que ambos modelos quieran 'Group.user_set'
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        help_text=_('The groups this user belongs to.'),
        blank=True,
        related_name='authentication_users',
        related_query_name='authentication_user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        help_text=_('Specific permissions for this user.'),
        blank=True,
        related_name='authentication_user_permissions',
        related_query_name='authentication_user_permission',
    )

    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    is_blocked = models.BooleanField(default=False)
    blocked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username

class LoginAttempt(models.Model):
    """Track login attempts for security analysis"""
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
