from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.models.query import QuerySet

from . import moderation
from .constants import (MODERATION_READY_STATE,
                        MODERATION_STATUS_APPROVED,
                        MODERATION_STATUS_REJECTED)
from .signals import post_many_moderation, pre_many_moderation


class ModeratedObjectQuerySet(QuerySet):
    def approve(self, cls, by, reason=None):
        self._send_signals_and_moderate(cls, MODERATION_STATUS_APPROVED, by, reason)

    def reject(self, cls, by, reason=None):
        self._send_signals_and_moderate(cls, MODERATION_STATUS_REJECTED, by, reason)

    def moderator(self, cls):
        return moderation.get_moderator(cls)

    def _send_signals_and_moderate(self, cls, new_status, by, reason):
        pre_many_moderation.send(sender=cls,
                                 queryset=self,
                                 status=new_status,
                                 by=by,
                                 reason=reason)

        self._moderate(cls, new_status, by, reason)

        post_many_moderation.send(sender=cls,
                                  queryset=self,
                                  status=new_status,
                                  by=by,
                                  reason=reason)

    def _moderate(self, cls, new_status, by, reason):
        mod = self.moderator(cls)
        ct = ContentType.objects.get_for_model(cls)

        update_kwargs = {
            'status': new_status,
            'on': datetime.now(),
            'by': by,
            'reason': reason,
        }
        if new_status == MODERATION_STATUS_APPROVED:
            update_kwargs['state'] = MODERATION_READY_STATE

        self.update(update_kwargs)

        mod.inform_users(self.exclude(changed_by=None).select_related('changed_by__email'))
