from django.contrib import admin 
from .models import DeviceResetRequest, ElectionSettings 
 
@admin.register(DeviceResetRequest) 
class DeviceResetRequestAdmin(admin.ModelAdmin): 
    list_display = ('tsc_number', 'full_name', 'status') 
 
@admin.register(ElectionSettings) 
class ElectionSettingsAdmin(admin.ModelAdmin): 
    list_display = ('election_name', 'status') 
