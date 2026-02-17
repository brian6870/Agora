from django import forms
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.voting.models import Candidate, Position, Team, Election, CandidateApplication
from apps.core.models import DeviceResetRequest
import re


class CandidateForm(forms.ModelForm):
    """Form for adding/editing candidates"""
    
    photo = forms.ImageField(
        label='Candidate Photo',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        required=False
    )
    
    class Meta:
        model = Candidate
        fields = ['election', 'position', 'team', 'full_name', 'photo', 'bio', 'manifesto', 'order', 'is_active']
        widgets = {
            'election': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'team': forms.Select(attrs={'class': 'form-select'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name'}),
            'bio': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Short biography'}),
            'manifesto': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5, 'placeholder': 'Election manifesto'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'election' in self.data:
            try:
                election_id = int(self.data.get('election'))
                self.fields['position'].queryset = Position.objects.filter(election_id=election_id).order_by('order')
                self.fields['team'].queryset = Team.objects.filter(election_id=election_id, is_active=True).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['position'].queryset = Position.objects.filter(election=self.instance.election).order_by('order')
            self.fields['team'].queryset = Team.objects.filter(election=self.instance.election, is_active=True).order_by('name')
    
    def clean_full_name(self):
        name = self.cleaned_data['full_name']
        if len(name) < 3:
            raise forms.ValidationError("Name must be at least 3 characters")
        return name.title()


class TeamForm(forms.ModelForm):
    """Form for adding/editing teams"""
    
    logo = forms.ImageField(
        label='Team Logo',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        required=False
    )
    
    class Meta:
        model = Team
        fields = ['election', 'name', 'acronym', 'logo', 'color_code', 'description', 'is_active', 'status']
        widgets = {
            'election': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Team name'}),
            'acronym': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Acronym (optional)'}),
            'color_code': forms.TextInput(attrs={'class': 'form-input', 'type': 'color'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def clean_acronym(self):
        acronym = self.cleaned_data.get('acronym', '')
        if acronym and len(acronym) > 10:
            raise ValidationError("Acronym must be 10 characters or less")
        return acronym.upper()
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        election = self.cleaned_data.get('election')
        
        if election and name:
            if Team.objects.filter(election=election, name__iexact=name).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
                raise ValidationError("Team name already exists in this election.")
        return name


class PositionForm(forms.ModelForm):
    """Form for adding/editing positions"""
    
    class Meta:
        model = Position
        fields = ['election', 'order', 'name', 'description', 'max_votes', 'is_active']
        widgets = {
            'election': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Position name'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'max_votes': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 10}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        election = cleaned_data.get('election')
        order = cleaned_data.get('order')
        name = cleaned_data.get('name')
        
        if election and order:
            if Position.objects.filter(election=election, order=order).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
                raise ValidationError(f"Position order {order} already exists.")
        
        if election and name:
            if Position.objects.filter(election=election, name__iexact=name).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
                raise ValidationError("Position name already exists.")
        
        return cleaned_data


class ElectionForm(forms.ModelForm):
    """Form for creating/editing elections"""
    
    class Meta:
        model = Election
        fields = [
            'name', 'election_type', 'county', 'description',
            'voting_date', 'voting_start_time', 'voting_end_time',
            'status', 'allow_voting', 'results_published',
            'auto_open', 'auto_close', 'auto_publish',
            'reminder_24h', 'reminder_1h', 'reminder_start'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Election name'}),
            'election_type': forms.Select(attrs={'class': 'form-select'}),
            'county': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'voting_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'voting_start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'voting_end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'allow_voting': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'results_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_close': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_publish': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_24h': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_1h': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_start': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import User
        counties = User.objects.filter(user_type='VOTER').values_list('county', flat=True).distinct().order_by('county')
        county_choices = [('', '-- Select County --')] + [(c, c) for c in counties if c]
        self.fields['county'].choices = county_choices
        self.fields['county'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        election_type = cleaned_data.get('election_type')
        county = cleaned_data.get('county')
        start_time = cleaned_data.get('voting_start_time')
        end_time = cleaned_data.get('voting_end_time')
        voting_date = cleaned_data.get('voting_date')
        
        if election_type == 'COUNTY' and not county:
            raise ValidationError("County is required for county-based elections.")
        
        if start_time and end_time and start_time >= end_time:
            raise ValidationError("End time must be after start time.")
        
        if voting_date and voting_date < timezone.now().date():
            raise ValidationError("Voting date cannot be in the past.")
        
        return cleaned_data


class VoterSearchForm(forms.Form):
    """Form for searching voters"""
    
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-input', 'placeholder': 'Search by name, TSC, ID...'
    }))
    
    kyc_status = forms.ChoiceField(required=False, choices=[('', 'All KYC')] + list(User.KYC_STATUS),
                                   widget=forms.Select(attrs={'class': 'form-select'}))
    
    account_status = forms.ChoiceField(required=False, choices=[('', 'All Status')] + list(User.ACCOUNT_STATUS),
                                      widget=forms.Select(attrs={'class': 'form-select'}))
    
    voted = forms.ChoiceField(required=False, choices=[
        ('', 'All'), ('yes', 'Has Voted'), ('no', 'Not Voted')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    
    tsc_verified = forms.ChoiceField(required=False, choices=[
        ('', 'All'), ('yes', 'Verified'), ('no', 'Not Verified')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    
    county = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import User
        counties = User.objects.filter(user_type='VOTER').values_list('county', flat=True).distinct().order_by('county')
        self.fields['county'].choices = [('', 'All Counties')] + [(c, c) for c in counties if c]

class DeviceResetProcessForm(forms.Form):
    """Form for processing device resets"""
    action = forms.ChoiceField(choices=[('approve', 'Approve'), ('reject', 'Reject')],
                              widget=forms.Select(attrs={'class': 'form-select'}))
    reason = forms.CharField(required=False, widget=forms.Textarea(
        attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Reason for rejection'}))


class BulkActionForm(forms.Form):
    """Form for bulk voter actions"""
    ACTION_CHOICES = [
        ('', '-- Select Action --'),
        ('verify_kyc', 'Verify KYC'),
        ('verify_tsc', 'Verify TSC'),
        ('suspend', 'Suspend Accounts'),
        ('activate', 'Activate Accounts'),
        ('delete', 'Delete Accounts'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    reason = forms.CharField(required=False, widget=forms.Textarea(
        attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Reason for action'}))
    confirm = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class CandidateApplicationReviewForm(forms.Form):
    """Form for reviewing candidate applications"""
    ACTION_CHOICES = [('approve', 'Approve'), ('reject', 'Reject')]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    rejection_reason = forms.CharField(required=False, widget=forms.Textarea(
        attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Reason for rejection'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(
        attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Admin notes'}))


class TeamApplicationReviewForm(forms.Form):
    """Form for reviewing team applications"""
    ACTION_CHOICES = [('approve', 'Approve'), ('reject', 'Reject')]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    rejection_reason = forms.CharField(required=False, widget=forms.Textarea(
        attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Reason for rejection'}))


class GeneralSettingsForm(forms.Form):
    """General system settings"""
    site_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-input'}))
    site_url = forms.URLField(widget=forms.URLInput(attrs={'class': 'form-input'}))
    support_email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-input'}))
    allow_registration = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    require_email_verification = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    require_kyc = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class SecuritySettingsForm(forms.Form):
    """Security settings"""
    min_password_length = forms.IntegerField(min_value=6, max_value=20, initial=8,
                                            widget=forms.NumberInput(attrs={'class': 'form-input'}))
    require_uppercase = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    require_lowercase = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    require_number = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    require_special = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class EmailSettingsForm(forms.Form):
    """Email settings"""
    smtp_host = forms.CharField(max_length=255, initial='pro.turbo-smtp.com',
                                widget=forms.TextInput(attrs={'class': 'form-input'}))
    smtp_port = forms.ChoiceField(choices=[
        ('587', '587 (TLS)'), ('465', '465 (SSL)'), ('25', '25 (Non-SSL)'),
        ('2525', '2525 (Non-SSL)'), ('25025', '25025 (SSL)')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    smtp_user = forms.CharField(max_length=255, initial='f37083ced9d0eab33b42',
                                widget=forms.TextInput(attrs={'class': 'form-input'}))
    smtp_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input'}), required=False)
    from_email = forms.EmailField(initial='noreply@agora.ke', widget=forms.EmailInput(attrs={'class': 'form-input'}))
    use_tls = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    use_ssl = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class BackupSettingsForm(forms.Form):
    """Backup settings"""
    backup_frequency = forms.ChoiceField(choices=[
        ('manual', 'Manual Only'), ('hourly', 'Hourly'), ('daily', 'Daily'),
        ('weekly', 'Weekly'), ('monthly', 'Monthly')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    backup_time = forms.TimeField(initial='02:00', widget=forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}))
    retention_days = forms.IntegerField(min_value=1, max_value=365, initial=30,
                                        widget=forms.NumberInput(attrs={'class': 'form-input'}))
    max_backups = forms.IntegerField(min_value=1, max_value=100, initial=10,
                                     widget=forms.NumberInput(attrs={'class': 'form-input'}))
    backup_database = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    backup_media = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    compress_backups = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class MaintenanceModeForm(forms.Form):
    """Maintenance mode form"""
    message = forms.CharField(initial='System under maintenance.',
                             widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}))
    duration = forms.IntegerField(min_value=5, max_value=1440, initial=30,
                                  widget=forms.NumberInput(attrs={'class': 'form-input'}))
    notify = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class NotificationForm(forms.Form):
    """Form for sending notifications"""
    recipients = forms.ChoiceField(choices=[
        ('all', 'All Admins'), ('admins', 'Admins Only'),
        ('super_admins', 'Super Admins Only'), ('specific', 'Specific Users')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    users = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 5}))
    type = forms.ChoiceField(choices=[
        ('INFO', 'Information'), ('SUCCESS', 'Success'), ('WARNING', 'Warning'),
        ('ERROR', 'Error'), ('ACTION_REQUIRED', 'Action Required')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    priority = forms.ChoiceField(choices=[
        ('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('URGENT', 'Urgent')
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-input'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}))
    action_url = forms.URLField(required=False, widget=forms.URLInput(attrs={'class': 'form-input'}))
    action_text = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={'class': 'form-input'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import User
        users = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN']).order_by('full_name')
        self.fields['users'].choices = [(u.id, f"{u.full_name} ({u.email})") for u in users]