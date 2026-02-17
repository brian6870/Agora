from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, AdminProfile, EmailVerificationOTP

class CustomUserAdmin(UserAdmin):
    list_display = ('tsc_number', 'full_name', 'email', 'user_type', 'kyc_status', 'has_voted', 'registered_at')
    list_filter = ('user_type', 'kyc_status', 'has_voted', 'county', 'is_active')
    search_fields = ('tsc_number', 'email', 'full_name', 'id_number', 'school')
    ordering = ('-registered_at',)
    readonly_fields = ('registered_at', 'voted_at', 'verified_at', 'vote_token', 'device_fingerprint')
    
    fieldsets = (
        (None, {'fields': ('tsc_number', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'id_number', 'phone_number', 'school', 'county')}),
        ('KYC Status', {'fields': ('kyc_status', 'id_front_status', 'id_back_status', 'face_photo_status')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'user_type', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'registered_at', 'verified_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('tsc_number', 'email', 'password1', 'password2', 'full_name', 'id_number', 'school', 'county', 'user_type'),
        }),
    )

class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'national_id', 'county_of_residence', 'is_verified', 'verified_at')
    list_filter = ('is_verified', 'county_of_residence')
    search_fields = ('user__full_name', 'national_id')
    readonly_fields = ('verified_at',)

class EmailVerificationOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used',)
    search_fields = ('email', 'otp')
    readonly_fields = ('created_at',)

# Register models
admin.site.register(User, CustomUserAdmin)
admin.site.register(AdminProfile, AdminProfileAdmin)
admin.site.register(EmailVerificationOTP, EmailVerificationOTPAdmin)

# Customize admin site
admin.site.site_header = 'Agora Administration'
admin.site.site_title = 'Agora Admin'
admin.site.index_title = 'Dashboard'