from django.contrib import admin 
from apps.voting.models import Position, Team, Candidate, Vote 
from apps.core.models import ElectionSettings, DeviceResetRequest 
 
@admin.register(Position) 
class PositionAdmin(admin.ModelAdmin): 
    list_display = ('order', 'name') 
 
@admin.register(Team) 
class TeamAdmin(admin.ModelAdmin): 
    list_display = ('name',) 
 
@admin.register(Candidate) 
class CandidateAdmin(admin.ModelAdmin): 
    list_display = ('full_name', 'position') 
