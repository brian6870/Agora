from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Election, Position, Candidate, Team, CandidateApplication, Vote

class ElectionForm(forms.ModelForm):
    """Form for creating/editing elections"""
    
    class Meta:
        model = Election
        fields = [
            'name', 'election_type', 'county', 'description',
            'voting_date', 'voting_start_time', 'voting_end_time',
            'status', 'allow_voting', 'auto_open', 'auto_close', 'auto_publish',
            'reminder_24h', 'reminder_1h', 'reminder_start'
        ]
        widgets = {
            'voting_date': forms.DateInput(attrs={'type': 'date'}),
            'voting_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'voting_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county'].required = False
        
        # If this is a county election, make county required
        if self.instance and self.instance.election_type == 'COUNTY':
            self.fields['county'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        election_type = cleaned_data.get('election_type')
        county = cleaned_data.get('county')
        voting_date = cleaned_data.get('voting_date')
        start_time = cleaned_data.get('voting_start_time')
        end_time = cleaned_data.get('voting_end_time')
        
        # Validate county for county elections
        if election_type == 'COUNTY' and not county:
            self.add_error('county', 'County is required for county-based elections')
        
        # Validate voting times
        if voting_date and start_time and end_time:
            # Combine date and time for comparison
            start_datetime = timezone.make_aware(
                datetime.combine(voting_date, start_time)
            )
            end_datetime = timezone.make_aware(
                datetime.combine(voting_date, end_time)
            )
            
            if end_datetime <= start_datetime:
                self.add_error('voting_end_time', 'End time must be after start time')
            
            # Check if election is in the past (for new elections)
            if not self.instance.pk and end_datetime < timezone.now():
                self.add_error('voting_date', 'Election cannot be scheduled in the past')
        
        return cleaned_data


class PositionForm(forms.ModelForm):
    """Form for creating/editing positions"""
    
    class Meta:
        model = Position
        fields = ['election', 'name', 'description', 'order', 'max_votes', 'is_active',
                  'require_team', 'require_manifesto', 'require_bio']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter elections to show only active ones
        self.fields['election'].queryset = Election.objects.all().order_by('-created_at')
        self.fields['election'].label_from_instance = lambda obj: f"{obj.name} ({obj.get_election_type_display()})"
    
    def clean_order(self):
        order = self.cleaned_data.get('order')
        election = self.cleaned_data.get('election')
        
        if order and election:
            # Check if order is unique within this election
            existing = Position.objects.filter(election=election, order=order)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f'Order {order} already exists for this election')
        
        return order
    
    def clean_max_votes(self):
        max_votes = self.cleaned_data.get('max_votes')
        if max_votes and (max_votes < 1 or max_votes > 10):
            raise ValidationError('Max votes must be between 1 and 10')
        return max_votes


class CandidateForm(forms.ModelForm):
    """Form for creating/editing candidates (admin only)"""
    
    class Meta:
        model = Candidate
        fields = ['election', 'position', 'team', 'voter', 'full_name',
                  'photo', 'bio', 'manifesto', 'order', 'is_active']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'manifesto': forms.Textarea(attrs={'rows': 4}),
            'photo': forms.FileInput(attrs={'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make voter field optional for admin creation
        self.fields['voter'].required = False
        self.fields['voter'].queryset = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED')
        
        # Filter positions by selected election
        if 'election' in self.data:
            try:
                election_id = int(self.data.get('election'))
                self.fields['position'].queryset = Position.objects.filter(election_id=election_id).order_by('order')
                self.fields['team'].queryset = Team.objects.filter(election_id=election_id, is_active=True)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['position'].queryset = Position.objects.filter(election=self.instance.election)
            self.fields['team'].queryset = Team.objects.filter(election=self.instance.election, is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        election = cleaned_data.get('election')
        position = cleaned_data.get('position')
        full_name = cleaned_data.get('full_name')
        
        # Validate that position belongs to the selected election
        if election and position and position.election != election:
            self.add_error('position', 'Selected position does not belong to this election')
        
        # Check for duplicate candidate in same election/position
        if election and position and full_name:
            duplicate = Candidate.objects.filter(
                election=election,
                position=position,
                full_name__iexact=full_name
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            
            if duplicate.exists():
                self.add_error('full_name', 'A candidate with this name already exists for this position')
        
        return cleaned_data


class TeamForm(forms.ModelForm):
    """Form for creating/editing teams"""
    
    class Meta:
        model = Team
        fields = ['election', 'name', 'acronym', 'color_code', 'logo', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'color_code': forms.TextInput(attrs={'type': 'color'}),
            'logo': forms.FileInput(attrs={'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['acronym'].required = False
        self.fields['logo'].required = False
        self.fields['election'].queryset = Election.objects.all().order_by('-created_at')
        self.fields['election'].label_from_instance = lambda obj: f"{obj.name} ({obj.get_election_type_display()})"
    
    def clean_acronym(self):
        acronym = self.cleaned_data.get('acronym')
        if acronym:
            acronym = acronym.upper()
        return acronym
    
    def clean(self):
        cleaned_data = super().clean()
        election = cleaned_data.get('election')
        name = cleaned_data.get('name')
        
        # Check for duplicate team name in same election
        if election and name:
            duplicate = Team.objects.filter(election=election, name__iexact=name)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            
            if duplicate.exists():
                self.add_error('name', 'A team with this name already exists for this election')
        
        return cleaned_data

class CandidateApplicationForm(forms.ModelForm):
    """Form for voters to apply as candidates"""
    
    class Meta:
        model = CandidateApplication
        fields = ['election', 'position', 'team', 'manifesto', 'bio', 'photo']
        widgets = {
            'manifesto': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Outline your vision and goals...'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about yourself...'}),
            'photo': forms.FileInput(attrs={'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.election = kwargs.pop('election', None)
        super().__init__(*args, **kwargs)
        
        # Make election field hidden but keep its value
        if self.election:
            self.fields['election'].initial = self.election
            self.fields['election'].widget = forms.HiddenInput()
            self.fields['election'].required = True  # Keep required for validation
        
        if self.election:
            # Only show ACTIVE positions for this election
            self.fields['position'].queryset = Position.objects.filter(
                election=self.election,
                is_active=True
            ).order_by('order')
            self.fields['position'].required = True
            
            # Only show APPROVED teams for this election
            self.fields['team'].queryset = Team.objects.filter(
                election=self.election,
                status='APPROVED',
                is_active=True
            ).order_by('name')
            self.fields['team'].required = False
        else:
            self.fields['position'].queryset = Position.objects.none()
            self.fields['team'].queryset = Team.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        election = cleaned_data.get('election')
        position = cleaned_data.get('position')
        team = cleaned_data.get('team')
        
        # If election is not in cleaned_data but we have self.election, use that
        if not election and self.election:
            election = self.election
            cleaned_data['election'] = self.election
        
        if not election:
            self.add_error('election', 'Election is required')
            return cleaned_data
        
        if not position:
            self.add_error('position', 'Position is required')
            return cleaned_data
        
        # Check if user already applied for this position
        if self.user and CandidateApplication.objects.filter(
            voter=self.user,
            election=election,
            position=position
        ).exists():
            self.add_error('position', 'You have already applied for this position')
        
        # Validate position belongs to election
        if position and position.election != election:
            self.add_error('position', 'Selected position does not belong to this election')
        
        # Validate team belongs to election and is approved
        if team:
            if team.election != election:
                self.add_error('team', 'Selected team does not belong to this election')
            elif team.status != 'APPROVED':
                self.add_error('team', 'Selected team is not approved yet')
        
        return cleaned_data
class VoteForm(forms.Form):
    """Form for vote submission"""
    votes = forms.JSONField()
    
    def clean_votes(self):
        votes = self.cleaned_data.get('votes', {})
        
        if not votes:
            raise ValidationError('No votes submitted')
        
        # Validate each vote
        for position_id, candidate_id in votes.items():
            try:
                position = Position.objects.get(id=position_id, is_active=True)
                candidate = Candidate.objects.get(id=candidate_id, position_id=position_id, is_active=True)
            except (Position.DoesNotExist, Candidate.DoesNotExist):
                raise ValidationError(f'Invalid vote for position {position_id}')
        
        return votes