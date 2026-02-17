from django import forms
from django.core.validators import RegexValidator, FileExtensionValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import User, AccountActionRequest
from apps.core.models import DeviceResetRequest
import re
import os 

# ==================== VOTER FORMS ====================

class VoterRegistrationForm(forms.ModelForm):
    """Form for voter registration with KYC and device binding"""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'}),
        validators=[validate_password]
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
    
    id_front = forms.ImageField(
        label='Front of ID',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    id_back = forms.ImageField(
        label='Back of ID (Optional)',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    face_photo = forms.ImageField(
        label='Face Photo / Selfie',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    
    terms_agreed = forms.BooleanField(
        label='I agree to the terms and conditions',
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )
    
    class Meta:
        model = User
        fields = [
            'tsc_number', 'id_number', 'full_name', 'email', 'school', 
            'county', 'phone_number'
        ]
        widgets = {
            'tsc_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'TSC Number'}),
            'id_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ID Number'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name as on ID'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'your@email.com'}),
            'school': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Name'}),
            'county': forms.Select(attrs={'class': 'form-select'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '07XX XXX XXX'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county'].choices = self.get_county_choices()
    
    def get_county_choices(self):
        """Return list of all Kenyan counties"""
        return [
            ('', '-- Select County --'),
            ('Mombasa', 'Mombasa'), ('Kwale', 'Kwale'), ('Kilifi', 'Kilifi'),
            ('Tana River', 'Tana River'), ('Lamu', 'Lamu'), ('Taita Taveta', 'Taita Taveta'),
            ('Garissa', 'Garissa'), ('Wajir', 'Wajir'), ('Mandera', 'Mandera'),
            ('Marsabit', 'Marsabit'), ('Isiolo', 'Isiolo'), ('Meru', 'Meru'),
            ('Tharaka Nithi', 'Tharaka Nithi'), ('Embu', 'Embu'), ('Kitui', 'Kitui'),
            ('Machakos', 'Machakos'), ('Makueni', 'Makueni'), ('Nyandarua', 'Nyandarua'),
            ('Nyeri', 'Nyeri'), ('Kirinyaga', 'Kirinyaga'), ("Murang'a", "Murang'a"),
            ('Kiambu', 'Kiambu'), ('Turkana', 'Turkana'), ('West Pokot', 'West Pokot'),
            ('Samburu', 'Samburu'), ('Trans Nzoia', 'Trans Nzoia'), ('Uasin Gishu', 'Uasin Gishu'),
            ('Elgeyo Marakwet', 'Elgeyo Marakwet'), ('Nandi', 'Nandi'), ('Baringo', 'Baringo'),
            ('Laikipia', 'Laikipia'), ('Nakuru', 'Nakuru'), ('Narok', 'Narok'),
            ('Kajiado', 'Kajiado'), ('Kericho', 'Kericho'), ('Bomet', 'Bomet'),
            ('Kakamega', 'Kakamega'), ('Vihiga', 'Vihiga'), ('Bungoma', 'Bungoma'),
            ('Busia', 'Busia'), ('Siaya', 'Siaya'), ('Kisumu', 'Kisumu'),
            ('Homa Bay', 'Homa Bay'), ('Migori', 'Migori'), ('Kisii', 'Kisii'),
            ('Nyamira', 'Nyamira'), ('Nairobi', 'Nairobi')
        ]
    
    def clean_tsc_number(self):
        tsc = self.cleaned_data.get('tsc_number', '').strip()
        if not tsc:
            raise ValidationError("TSC number is required")
        if not re.match(r'^\d+$', tsc):
            raise ValidationError("TSC number must contain only digits")
        if User.objects.filter(tsc_number=tsc).exists():
            raise ValidationError("This TSC number is already registered")
        return tsc
    
    def clean_id_number(self):
        id_num = self.cleaned_data.get('id_number', '').strip()
        if not id_num:
            raise ValidationError("ID number is required")
        if not re.match(r'^\d+$', id_num):
            raise ValidationError("ID number must contain only digits")
        if User.objects.filter(id_number=id_num).exists():
            raise ValidationError("This ID number is already registered")
        return id_num
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError("Email is required")
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered")
        return email
    
    def clean_full_name(self):
        name = self.cleaned_data.get('full_name', '').strip()
        if not name:
            raise ValidationError("Full name is required")
        if len(name) < 3:
            raise ValidationError("Full name must be at least 3 characters")
        return name
    
    def clean_school(self):
        school = self.cleaned_data.get('school', '').strip()
        if not school:
            raise ValidationError("School name is required")
        return school
    
    def clean_county(self):
        county = self.cleaned_data.get('county')
        if not county:
            raise ValidationError("County is required")
        return county
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and not re.match(r'^07\d{8}$', phone):
            raise ValidationError("Phone number must be in format 07XXXXXXXX")
        return phone
    
    def clean_id_front(self):
        id_front = self.cleaned_data.get('id_front')
        if not id_front:
            raise ValidationError("Front of ID is required")
        if id_front.size > 10 * 1024 * 1024:
            raise ValidationError("Image size must be less than 10MB")
        return id_front
    
    def clean_face_photo(self):
        face_photo = self.cleaned_data.get('face_photo')
        if not face_photo:
            raise ValidationError("Face photo is required")
        if face_photo.size > 10 * 1024 * 1024:
            raise ValidationError("Image size must be less than 10MB")
        return face_photo
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords do not match")
            raise ValidationError("Passwords do not match")
        
        if not cleaned_data.get('terms_agreed'):
            raise ValidationError("You must agree to the terms and conditions")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.user_type = 'VOTER'
        user.username = user.tsc_number
        user.kyc_status = 'PENDING'
        user.email_verified = True
        user.account_status = 'PENDING'
        user.id_front_status = 'UPLOADED'
        if self.cleaned_data.get('id_back'):
            user.id_back_status = 'UPLOADED'
        user.face_photo_status = 'UPLOADED'
        user.kyc_submitted_at = timezone.now()
        
        if commit:
            user.save()
        return user


class VoterLoginForm(forms.Form):
    """Form for voter login"""
    tsc_number = forms.CharField(
        label='TSC Number',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter your TSC number'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter your password'})
    )
    remember_me = forms.BooleanField(
        label='Remember me',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )
    
    def clean_tsc_number(self):
        tsc = self.cleaned_data.get('tsc_number', '').strip()
        if not tsc:
            raise ValidationError("TSC number is required")
        return tsc


# ==================== DEVICE RESET FORMS ====================

class DeviceResetRequestForm(forms.ModelForm):
    """Form for voters to request device reset"""
    confirm_statement = forms.BooleanField(
        label='I understand that this request must be made at least 3 days before voting day',
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )
    
    class Meta:
        model = DeviceResetRequest
        fields = ['tsc_number', 'id_number', 'full_name', 'reason']
        widgets = {
            'tsc_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'TSC Number'}),
            'id_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ID Number'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'reason': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Explain why you need to reset your device...'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('confirm_statement'):
            raise ValidationError("You must confirm the 3-day rule")
        
        tsc = cleaned_data.get('tsc_number', '').strip()
        id_num = cleaned_data.get('id_number', '').strip()
        
        if tsc and id_num:
            if not User.objects.filter(tsc_number=tsc, id_number=id_num).exists():
                raise ValidationError("No voter found with these credentials")
        return cleaned_data


# ==================== PASSWORD RESET FORMS ====================

class PasswordResetRequestForm(forms.Form):
    """Form for requesting password reset with email OTP"""
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'your@email.com'})
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError("Email is required")
        if not User.objects.filter(email=email).exists():
            raise ValidationError("No account found with this email address")
        return email


class PasswordResetVerifyForm(forms.Form):
    """Form for verifying OTP and setting new password"""
    otp = forms.CharField(
        label='OTP Code',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'class': 'form-input text-center', 'placeholder': '123456'})
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter new password'}),
        validators=[validate_password]
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm new password'})
    )
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp', '').strip()
        if not otp or len(otp) != 6 or not otp.isdigit():
            raise ValidationError("Please enter a valid 6-digit OTP")
        return otp
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            self.add_error('new_password2', "Passwords do not match")
            raise ValidationError("Passwords do not match")
        
        return cleaned_data


# ==================== ACCOUNT DELETION FORMS ====================

class AccountDeletionForm(forms.Form):
    """Form for users to request account deletion"""
    reason = forms.CharField(
        label='Reason for deletion',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Tell us why you\'re leaving (optional)'
        })
    )
    confirm = forms.BooleanField(
        label='I understand that this action is permanent and cannot be undone',
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )
    
    def clean_confirm(self):
        confirm = self.cleaned_data.get('confirm')
        if not confirm:
            raise ValidationError("You must confirm that you understand this action is permanent")
        return confirm


# ==================== PROFILE FORMS ====================

class UserProfileForm(forms.ModelForm):
    """Form for users to edit their profile"""
    class Meta:
        model = User
        fields = ['full_name', 'phone_number', 'school']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
            'school': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Name'}),
        }
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and not re.match(r'^07\d{8}$', phone):
            raise ValidationError("Phone number must be in format 07XXXXXXXX")
        return phone


# ==================== ADMIN FORMS ====================

class AdminLoginForm(forms.Form):
    """Form for admin login"""
    username = forms.CharField(
        label='Admin ID / Email',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter your admin ID or email'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter your password'})
    )
    remember_me = forms.BooleanField(
        label='Remember me',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )


class AdminRegistrationForm(forms.ModelForm):
    """Form for admin registration with proper validation"""
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'}),
        validators=[validate_password]
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
    id_front = forms.ImageField(
        label='Front of ID Document',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        error_messages={
            'invalid': 'Please upload a valid image file (JPG, JPEG, or PNG)',
            'required': 'Front of ID document is required'
        }
    )
    id_back = forms.ImageField(
        label='Back of ID Document',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        required=True,
        error_messages={
            'invalid': 'Please upload a valid image file (JPG, JPEG, or PNG)',
            'required': 'Back of ID document is required'
        }
    )
    selfie_photo = forms.ImageField(
        label='Selfie Photo',
        widget=forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        error_messages={
            'invalid': 'Please upload a valid image file (JPG, JPEG, or PNG)',
            'required': 'Selfie photo is required'
        }
    )
    terms_agreed = forms.BooleanField(
        label='I agree to the terms and conditions',
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'}),
        error_messages={
            'required': 'You must agree to the terms and conditions to register'
        }
    )
    
    class Meta:
        model = User
        fields = ['full_name', 'email', 'id_number', 'county', 'phone_number']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'}),
            'id_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'National ID Number', 'maxlength': '20'}),
            'county': forms.Select(attrs={'class': 'form-select'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county'].choices = self.get_county_choices()
        # Make phone_number optional
        self.fields['phone_number'].required = False
        
    def get_county_choices(self):
        return [
            ('', '-- Select County --'),
            ('Mombasa', 'Mombasa'), ('Kwale', 'Kwale'), ('Kilifi', 'Kilifi'),
            ('Tana River', 'Tana River'), ('Lamu', 'Lamu'), ('Taita Taveta', 'Taita Taveta'),
            ('Garissa', 'Garissa'), ('Wajir', 'Wajir'), ('Mandera', 'Mandera'),
            ('Marsabit', 'Marsabit'), ('Isiolo', 'Isiolo'), ('Meru', 'Meru'),
            ('Tharaka Nithi', 'Tharaka Nithi'), ('Embu', 'Embu'), ('Kitui', 'Kitui'),
            ('Machakos', 'Machakos'), ('Makueni', 'Makueni'), ('Nyandarua', 'Nyandarua'),
            ('Nyeri', 'Nyeri'), ('Kirinyaga', 'Kirinyaga'), ("Murang'a", "Murang'a"),
            ('Kiambu', 'Kiambu'), ('Turkana', 'Turkana'), ('West Pokot', 'West Pokot'),
            ('Samburu', 'Samburu'), ('Trans Nzoia', 'Trans Nzoia'), ('Uasin Gishu', 'Uasin Gishu'),
            ('Elgeyo Marakwet', 'Elgeyo Marakwet'), ('Nandi', 'Nandi'), ('Baringo', 'Baringo'),
            ('Laikipia', 'Laikipia'), ('Nakuru', 'Nakuru'), ('Narok', 'Narok'),
            ('Kajiado', 'Kajiado'), ('Kericho', 'Kericho'), ('Bomet', 'Bomet'),
            ('Kakamega', 'Kakamega'), ('Vihiga', 'Vihiga'), ('Bungoma', 'Bungoma'),
            ('Busia', 'Busia'), ('Siaya', 'Siaya'), ('Kisumu', 'Kisumu'),
            ('Homa Bay', 'Homa Bay'), ('Migori', 'Migori'), ('Kisii', 'Kisii'),
            ('Nyamira', 'Nyamira'), ('Nairobi', 'Nairobi')
        ]
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError("Email is required")
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered")
        return email
    
    def clean_id_number(self):
        id_num = self.cleaned_data.get('id_number', '').strip()
        if not id_num:
            raise ValidationError("National ID is required")
        if not re.match(r'^\d+$', id_num):
            raise ValidationError("ID number must contain only digits")
        if len(id_num) > 20:
            raise ValidationError("ID number must not exceed 20 characters")
        if User.objects.filter(id_number=id_num).exists():
            raise ValidationError("This ID number is already registered")
        return id_num
    
    def clean_full_name(self):
        name = self.cleaned_data.get('full_name', '').strip()
        if not name:
            raise ValidationError("Full name is required")
        if len(name) < 3:
            raise ValidationError("Full name must be at least 3 characters")
        return name
    
    def clean_county(self):
        county = self.cleaned_data.get('county')
        if not county:
            raise ValidationError("County is required")
        return county
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and not re.match(r'^07\d{8}$', phone):
            raise ValidationError("Phone number must be in format 07XXXXXXXX")
        return phone
    
    def clean_id_front(self):
        id_front = self.cleaned_data.get('id_front')
        if not id_front:
            raise ValidationError("Front of ID is required")
        
        # Check file size (max 10MB)
        if id_front.size > 10 * 1024 * 1024:
            raise ValidationError("Image size must be less than 10MB")
        
        # Check file extension
        ext = os.path.splitext(id_front.name)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            raise ValidationError("Only JPG, JPEG, and PNG files are allowed")
        
        return id_front
    
    def clean_id_back(self):
        id_back = self.cleaned_data.get('id_back')
        if not id_back:
            raise ValidationError("Back of ID is required")
        
        if id_back.size > 10 * 1024 * 1024:
            raise ValidationError("Image size must be less than 10MB")
        
        ext = os.path.splitext(id_back.name)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            raise ValidationError("Only JPG, JPEG, and PNG files are allowed")
        
        return id_back
    
    def clean_selfie_photo(self):
        selfie = self.cleaned_data.get('selfie_photo')
        if not selfie:
            raise ValidationError("Selfie photo is required")
        
        if selfie.size > 10 * 1024 * 1024:
            raise ValidationError("Image size must be less than 10MB")
        
        ext = os.path.splitext(selfie.name)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            raise ValidationError("Only JPG, JPEG, and PNG files are allowed")
        
        return selfie
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        terms_agreed = cleaned_data.get('terms_agreed')
        
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords do not match")
            raise ValidationError("Passwords do not match")
        
        if not terms_agreed:
            self.add_error('terms_agreed', "You must agree to the terms and conditions")
            raise ValidationError("You must agree to the terms and conditions")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.user_type = 'ADMIN'
        user.username = self.cleaned_data['email']
        user.kyc_status = 'PENDING'
        user.email_verified = True
        user.is_active = False  # Admin accounts need approval
        user.account_status = 'PENDING'  # Set status to pending
        
        if commit:
            user.save()
            # Create AdminProfile
            from .models import AdminProfile
            AdminProfile.objects.create(
                user=user,
                national_id=self.cleaned_data['id_number'],
                county_of_residence=self.cleaned_data['county'],
                id_document=self.cleaned_data['id_front'],
                selfie_photo=self.cleaned_data['selfie_photo'],
                is_verified=False
            )
        return user
class AdminPasswordResetRequestForm(forms.Form):
    """Form for admin password reset request"""
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'admin@example.com'})
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not User.objects.filter(email=email, user_type__in=['ADMIN', 'SUPER_ADMIN']).exists():
            raise ValidationError("No admin account found with this email address")
        return email


class AdminPasswordResetVerifyForm(forms.Form):
    """Form for admin password reset verification"""
    otp = forms.CharField(
        label='OTP Code',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'class': 'form-input text-center', 'placeholder': '123456'})
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'}),
        validators=[validate_password]
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp', '').strip()
        if not otp or len(otp) != 6 or not otp.isdigit():
            raise ValidationError("Please enter a valid 6-digit OTP")
        return otp
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            self.add_error('new_password2', "Passwords do not match")
            raise ValidationError("Passwords do not match")
        
        return cleaned_data


class AdminDeviceResetRequestForm(forms.ModelForm):
    """Form for admin device reset request"""
    
    confirm_statement = forms.BooleanField(
        label='I understand that this request requires admin approval',
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )
    
    class Meta:
        model = DeviceResetRequest
        fields = ['tsc_number', 'id_number', 'full_name', 'reason']
        widgets = {
            'tsc_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Admin ID/TSC Number'}),
            'id_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ID Number'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'reason': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Explain why you need to reset your admin device...'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data.get('confirm_statement'):
            raise ValidationError("You must confirm the approval requirement")
        
        tsc = cleaned_data.get('tsc_number', '').strip()
        id_num = cleaned_data.get('id_number', '').strip()
        
        if tsc and id_num:
            try:
                user = User.objects.get(tsc_number=tsc, id_number=id_num, user_type__in=['ADMIN', 'SUPER_ADMIN'])
            except User.DoesNotExist:
                raise ValidationError("No admin found with these credentials")
        return cleaned_data


# ==================== ADMIN ACTION FORMS ====================

class AdminApprovalForm(forms.Form):
    """Form for superusers to approve/reject admin registrations"""
    admin_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        widget=forms.RadioSelect
    )
    admin_id_number = forms.CharField(
        label='Admin ID Number',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Assign a unique admin ID'})
    )
    reason = forms.CharField(
        label='Reason (if rejecting)',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        reason = cleaned_data.get('reason')
        
        if action == 'reject' and not reason:
            raise ValidationError("Please provide a reason for rejection")
        
        return cleaned_data


class SuspendAccountForm(forms.Form):
    """Form for admins to suspend user accounts"""
    user_identifier = forms.CharField(
        label='TSC Number or Email',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter TSC number or email'})
    )
    reason = forms.CharField(
        label='Reason for suspension',
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Enter reason for suspension'})
    )
    duration = forms.ChoiceField(
        label='Suspension duration',
        choices=[
            ('3', '3 days'),
            ('7', '7 days'),
            ('30', '30 days'),
            ('permanent', 'Permanent'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_user_identifier(self):
        identifier = self.cleaned_data.get('user_identifier', '').strip()
        if not identifier:
            raise ValidationError("User identifier is required")
        
        # Check if user exists
        user = None
        if '@' in identifier:
            user = User.objects.filter(email=identifier).first()
        else:
            user = User.objects.filter(tsc_number=identifier).first()
        
        if not user:
            raise ValidationError("No user found with this identifier")
        
        return identifier


class BulkActionForm(forms.Form):
    """Form for bulk actions on users"""
    action = forms.ChoiceField(
        choices=[
            ('verify_kyc', 'Verify KYC'),
            ('verify_tsc', 'Verify TSC'),
            ('suspend', 'Suspend'),
            ('activate', 'Activate'),
            ('delete', 'Delete'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    user_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )