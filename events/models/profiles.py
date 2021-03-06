from django.db import models
from django.contrib.sites.models import Site
from django.contrib.auth.models import User, Group, AnonymousUser
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.conf import settings

from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill

from .locale import *
from .. import location
from ..utils import slugify

import uuid
import pytz
import datetime
import hashlib

class UserProfile(models.Model):
    " Store profile information about a user "

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    realname = models.CharField(verbose_name=_("Real Name"), max_length=150, blank=True)
    tz = models.CharField(max_length=32, verbose_name=_('Timezone'), default='UTC', choices=location.TimezoneChoices(), blank=False, null=False)
    avatar = ProcessedImageField(verbose_name=_("Photo Image"),
                                           upload_to='avatars',
                                           processors=[ResizeToFill(128, 128)],
                                           format='PNG',
                                           blank=True)
    city = models.ForeignKey(City, verbose_name=_('Home city'), null=True, blank=True, on_delete=models.CASCADE)

    web_url = models.URLField(verbose_name=_('Website URL'), blank=True, null=True)
    twitter = models.CharField(verbose_name=_('Twitter Name'), max_length=32, blank=True, null=True)
    facebook = models.URLField(verbose_name=_('Facebook URL'), max_length=32, blank=True, null=True)

    send_notifications = models.BooleanField(verbose_name=_('Send notification emails'), default=True)

    secret_key = models.UUIDField(default=uuid.uuid4, editable=True)

    categories = models.ManyToManyField('Category', blank=True)
    topics = models.ManyToManyField('Topic', blank=True)

    class Meta:
        ordering = ('user__username',)

    def __str__(self):
        try:
            if self.realname:
                return self.realname
            return "%s" % self.user.username
        except:
            return "Unknown Profile"

    def avatar_url(self):
        try:
            if self.avatar is None or self.avatar.name is None:
                return settings.STATIC_URL + 'img/avatar_placeholder.png'
            elif self.avatar.name.startswith('http'):
                return self.avatar.name
            else:
                return self.avatar.url
        except:
            return settings.STATIC_URL + 'img/avatar_placeholder.png'

    def get_timezone(self):
        try:
            return pytz.timezone(self.tz)
        except:
            return pytz.utc
    timezone = property(get_timezone)

    def tolocaltime(self, dt):
        as_utc = pytz.utc.localize(dt)
        return as_utc.astimezone(self.timezone)

    def fromlocaltime(self, dt):
        local = self.timezone.localize(dt)
        return local.astimezone(pytz.utc)

    @property
    def administering(self):
        return [member.team for member in Member.objects.filter(user=self, role=Member.ADMIN)]

    @property
    def moderating(self):
        return [member.team for member in Member.objects.filter(user=self, role__in=(Member.ADMIN, Member.MODERATOR))]

    def can_create_event(self, team):
        try:
            if self.user.is_superuser:
                return True
        except:
            return False
        if not self.user_id:
            return False
        if team.owner_profile == self:
            return True
        if self in team.moderators:
            return True
        return False

    def can_edit_series(self, series):
        try:
            if self.user.is_superuser:
                return True
        except:
            return False
        if series.created_by == self:
            return True
        if series.team.owner_profile == self:
            return True
        if self in series.team.moderators:
            return True
        return False

    def can_edit_event(self, event):
        try:
            if self.user.is_superuser:
                return True
        except:
            return False
        if event.created_by == self:
            return True
        if event.team.owner_profile == self:
            return True
        if self in event.team.moderators:
            return True
        return False

    def can_create_common_event(self, org):
        try:
            if self.user.is_superuser:
                return True
        except:
            return False
        if not self.user_id:
            return False
        if org.owner_profile == self:
            return True
        return False

    def can_edit_team(self, team):
        try:
            if self.user.is_superuser:
                return True
        except:
            return False
        if team.owner_profile == self:
            return True
        if self in team.moderators:
            return True
        return False

def get_user_timezone(username):
    # TODO: find a smarter way to get timezone
    return 'UTC'

def _getUserProfile(self):
    if not self.is_authenticated:
        return UserProfile()

    profile, created = UserProfile.objects.get_or_create(user=self)

    if created:
        profile.tz = get_user_timezone(self.username)
        if self.first_name:
            if self.last_name:
                profile.realname = '%s %s' % (self.first_name, self.last_name)
            else:
                profile.realname = self.first_name

        if self.email:
            h = hashlib.md5()
            h.update(bytearray(profile.user.email, 'utf8'))
            profile.avatar = 'http://www.gravatar.com/avatar/%s.jpg?d=mm' % h.hexdigest()

        profile.save()

    return profile

def _getAnonProfile(self):
    return UserProfile()

User.profile = property(_getUserProfile)
AnonymousUser.profile = property(_getAnonProfile)

class Organization(models.Model):
    name = models.CharField(max_length=256, null=False, blank=False)
    slug = models.CharField(max_length=256, null=False, blank=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)

    owner_profile = models.ForeignKey(UserProfile, related_name='owned_orgs', blank=False, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return u'%s' % (self.name)

class Team(models.Model):
    name = models.CharField(_("Team Name"), max_length=256, null=False, blank=False)
    organization = models.ForeignKey(Organization, related_name='teams', null=True, blank=True, on_delete=models.CASCADE)

    description = models.TextField(blank=True, null=True)

    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    spr = models.ForeignKey(SPR, null=True, blank=True, on_delete=models.CASCADE)
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.CASCADE)

    web_url = models.URLField(_("Website"), null=True, blank=True)
    email = models.EmailField(_("Email Address"), null=True, blank=True)

    created_date = models.DateField(_("Date Created"), default=timezone.now, null=True, blank=True)

    owner_profile = models.ForeignKey(UserProfile, related_name='owned_teams', null=True, on_delete=models.CASCADE)
    admin_profiles = models.ManyToManyField(UserProfile, related_name='admins', blank=True)
    contact_profiles = models.ManyToManyField(UserProfile, related_name='contacts', blank=True)

    cover_img = models.URLField(_("Team Photo"), null=True, blank=True)
    languages = models.ManyToManyField(Language, blank=True)
    active = models.BooleanField(_("Active Team"), default=True)
    tz = models.CharField(max_length=32, verbose_name=_('Default Timezone'), default='UTC', choices=location.TimezoneChoices(), blank=False, null=False, help_text=_('The most commonly used timezone for this Team.'))

    members = models.ManyToManyField(UserProfile, through='Member', related_name="memberships", blank=True)

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, blank=False, null=True)
    topics = models.ManyToManyField('Topic', blank=True)

    is_premium = models.BooleanField(default=settings.EVENTS_TEAMS_DEFAULT_PREMIUM)
    premium_by = models.ForeignKey(UserProfile, related_name='premium_teams', null=True, on_delete=models.SET_NULL)
    premium_started = models.DateTimeField(blank=True, null=True)
    premium_expires = models.DateTimeField(blank=True, null=True)

    @property
    def location_name(self):
        if self.city:
            return str(self.city)
        elif self.spr:
            return str(self.spr)
        elif self.country:
            return str(self.country)
        else:
            return ''

    @property
    def administrators(self):
        return [member.user for member in Member.objects.filter(team=self, role=Member.ADMIN)]

    @property
    def moderators(self):
        return [member.user for member in Member.objects.filter(team=self, role__in=(Member.ADMIN, Member.MODERATOR))]

    def __str__(self):
        return u'%s' % (self.name)

    def save(self, *args, **kwargs):
        if self.city is not None:
            self.spr = self.city.spr
            self.country = self.spr.country
        super().save(*args, **kwargs)  # Call the "real" save() method.


class Member(models.Model):
    NORMAL=0
    MODERATOR=1
    ADMIN=2
    ROLES = [
        (NORMAL, _("Normal")),
        (MODERATOR, _("Moderator")),
        (ADMIN, _("Administrator"))
    ]
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    role = models.SmallIntegerField(_("Member Role"), choices=ROLES, default=NORMAL, db_index=True)
    joined_date = models.DateTimeField(default=datetime.datetime.now)

    @property
    def role_name(self):
        return Member.ROLES[self.role][1]

    def __str__(self):
        return '%s in %s' % (self.user, self.team)

class Category(models.Model):
    name = models.CharField(max_length=256)
    description = models.TextField()
    slug = models.CharField(max_length=256, blank=True)
    img_url = models.URLField(blank=False, null=False)

    class Meta:
        verbose_name_plural = 'Categories'
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Topic(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=False, blank=False)
    name = models.CharField(max_length=256)
    slug = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

