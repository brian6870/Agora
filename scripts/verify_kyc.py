
#!/usr/bin/env python
"""Script to manually verify KYC documents"""
import os
import sys
import django

sys.path.append('/var/www/agora')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings')
django.setup()

from apps.accounts.models import User
from django.utils import timezone

def verify_pending_kyc(admin_tsc):
    """Verify all pending KYC submissions"""
    try:
        admin = User.objects.get(tsc_number=admin_tsc, user_type='ADMIN')
    except User.DoesNotExist:
        print(f"Admin with TSC {admin_tsc} not found")
        return
    
    pending = User.objects.filter(kyc_status='PENDING', user_type='VOTER')
    print(f"Found {pending.count()} pending KYC submissions")
    
    for voter in pending:
        print(f"\nVerifying: {voter.full_name} (TSC: {voter.tsc_number})")
        print(f"School: {voter.school}")
        print(f"ID Front: {voter.id_front}")
        print(f"Face Photo: {voter.face_photo}")
        
        response = input("Approve? (y/n/q): ").lower()
        
        if response == 'y':
            voter.kyc_status = 'VERIFIED'
            voter.verified_at = timezone.now()
            voter.verified_by = admin
            voter.save()
            print("✓ Verified")
        elif response == 'n':
            voter.kyc_status = 'REJECTED'
            voter.save()
            print("✗ Rejected")
        elif response == 'q':
            break
    
    print("\nKYC verification complete")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python verify_kyc.py <admin_tsc_number>")
        sys.exit(1)
    
    verify_pending_kyc(sys.argv[1])