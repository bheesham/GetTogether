from django.utils.translation import ugettext_lazy as _

from django.contrib import messages
from django.contrib.auth import logout as logout_user
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse

from events.models.profiles import Organization, Team, UserProfile, Member
from events.models.events import Event, CommonEvent, Place, Attendee
from events.forms import TeamForm, NewTeamForm, DeleteTeamForm
from events import location

import datetime
import simplejson

# Create your views here.
def teams_list(request, *args, **kwargs):
    if not request.user.is_authenticated:
        return redirect('all-teams')

    teams = request.user.profile.memberships.all().distinct()
    geo_ip = location.get_geoip(request)
    context = {
        'active': 'my',
        'teams': sorted(teams, key=lambda team: location.team_distance_from(geo_ip.latlng, team)),
    }
    return render(request, 'get_together/teams/list_teams.html', context)

def teams_list_all(request, *args, **kwargs):
    teams = Team.objects.all()
    geo_ip = location.get_geoip(request)
    context = {
        'active': 'all',
        'teams': sorted(teams, key=lambda team: location.team_distance_from(geo_ip.latlng, team)),
    }
    return render(request, 'get_together/teams/list_teams.html', context)

def show_team(request, team_id, *args, **kwargs):
    team = get_object_or_404(Team, id=team_id)
    upcoming_events = Event.objects.filter(team=team, end_time__gt=datetime.datetime.now()).order_by('start_time')
    recent_events = Event.objects.filter(team=team, end_time__lte=datetime.datetime.now()).order_by('-start_time')[:5]
    context = {
        'team': team,
        'upcoming_events': upcoming_events,
        'recent_events': recent_events,
        'is_member': request.user.profile in team.members.all(),
        'member_list': Member.objects.filter(team=team).order_by('-role', 'joined_date'),
        'can_create_event': request.user.profile.can_create_event(team),
        'can_edit_team': request.user.profile.can_edit_team(team),
    }
    return render(request, 'get_together/teams/show_team.html', context)

def create_team(request, *args, **kwargs):
    if request.method == 'GET':
        form = NewTeamForm()

        context = {
            'team_form': form,
        }
        return render(request, 'get_together/teams/create_team.html', context)
    elif request.method == 'POST':
        form = NewTeamForm(request.POST)
        if form.is_valid():
            new_team = form.save()
            new_team.owner_profile = request.user.profile
            new_team.save()
            Member.objects.create(team=new_team, user=request.user.profile, role=Member.ADMIN)
            return redirect('show-team', team_id=new_team.pk)
        else:
            context = {
                'team_form': form,
            }
            return render(request, 'get_together/teams/create_team.html', context)
    else:
     return redirect('home')

def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if not request.user.profile.can_edit_team(team):
        messages.add_message(request, messages.WARNING, message=_('You can not make changes to this team.'))
        return redirect('show-team', team_id=team.pk)

    if request.method == 'GET':
        form = TeamForm(instance=team)

        context = {
            'team': team,
            'team_form': form,
        }
        return render(request, 'get_together/teams/edit_team.html', context)
    elif request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            new_team = form.save()
            new_team.owner_profile = request.user.profile
            new_team.save()
            return redirect('show-team', team_id=new_team.pk)
        else:
            context = {
                'team': team,
                'team_form': form,
            }
            return render(request, 'get_together/teams/edit_team.html', context)
    else:
     return redirect('home')

def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if not request.user.profile.can_edit_team(team):
        messages.add_message(request, messages.WARNING, message=_('You can not make changes to this team.'))
        return redirect('show-team', team_id)

    if request.method == 'GET':
        form = DeleteTeamForm()

        context = {
            'team': team,
            'delete_form': form,
        }
        return render(request, 'get_together/teams/delete_team.html', context)
    elif request.method == 'POST':
        form = DeleteTeamForm(request.POST)
        if form.is_valid() and form.cleaned_data['confirm']:
            team.delete()
            return redirect('teams')
        else:
            context = {
                'team': team,
                'delete_form': form,
            }
            return render(request, 'get_together/teams/delete_team.html', context)
    else:
     return redirect('home')

def show_org(request, org_slug):
    org = get_object_or_404(Organization, slug=org_slug)
    upcoming_events = CommonEvent.objects.filter(organization=org, end_time__gt=datetime.datetime.now()).order_by('start_time')
    recent_events = CommonEvent.objects.filter(organization=org, end_time__lte=datetime.datetime.now()).order_by('-start_time')[:5]
    context = {
        'org': org,
        'upcoming_events': upcoming_events,
        'recent_events': recent_events,
        'member_list': Team.objects.filter(organization=org).order_by('name'),
        'can_create_event': request.user.profile.can_create_common_event(org),
    }
    return render(request, 'get_together/orgs/show_org.html', context)


