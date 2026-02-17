// static/js/registration.js
// Multi-step registration flow

class RegistrationFlow {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 4;
        this.formData = {};
        this.init();
    }
    
    init() {
        this.loadSavedData();
        this.updateStepDisplay();
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.querySelectorAll('.next-step').forEach(btn => {
            btn.addEventListener('click', () => this.nextStep());
        });
        
        document.querySelectorAll('.prev-step').forEach(btn => {
            btn.addEventListener('click', () => this.prevStep());
        });
        
        // Form field change tracking
        document.querySelectorAll('input, select, textarea').forEach(field => {
            field.addEventListener('change', (e) => {
                this.formData[e.target.name] = e.target.value;
                this.saveToSession();
            });
        });
        
        // File upload preview
        document.querySelectorAll('input[type="file"]').forEach(input => {
            input.addEventListener('change', (e) => this.handleFileUpload(e));
        });
    }
    
    nextStep() {
        if (!this.validateStep(this.currentStep)) return;
        
        this.currentStep++;
        this.updateStepDisplay();
        this.saveToSession();
    }
    
    prevStep() {
        this.currentStep--;
        this.updateStepDisplay();
    }
    
    updateStepDisplay() {
        // Hide all steps
        document.querySelectorAll('.step-content').forEach(el => {
            el.style.display = 'none';
        });
        
        // Show current step
        const currentEl = document.getElementById(`step-${this.currentStep}`);
        if (currentEl) currentEl.style.display = 'block';
        
        // Update progress indicators
        this.updateProgressBars();
        this.updateStepCircles();
    }
    
    updateProgressBars() {
        const progress = (this.currentStep / this.totalSteps) * 100;
        const bars = document.querySelectorAll('.progress-fill');
        
        bars.forEach(bar => {
            bar.style.width = `${progress}%`;
        });
    }
    
    updateStepCircles() {
        for (let i = 1; i <= this.totalSteps; i++) {
            const circle = document.getElementById(`step-circle-${i}`);
            if (!circle) continue;
            
            if (i < this.currentStep) {
                circle.innerHTML = '✓';
                circle.style.background = 'var(--success)';
            } else if (i === this.currentStep) {
                circle.innerHTML = i;
                circle.style.background = 'var(--accent-color)';
            } else {
                circle.innerHTML = i;
                circle.style.background = 'var(--bg-primary)';
                circle.style.color = 'var(--text-secondary)';
            }
        }
    }
    
    validateStep(step) {
        const stepEl = document.getElementById(`step-${step}`);
        const required = stepEl.querySelectorAll('[required]');
        
        for (let field of required) {
            if (!field.value) {
                this.showError(`Please fill in all required fields`);
                field.focus();
                return false;
            }
            
            if (field.type === 'email' && !this.validateEmail(field.value)) {
                this.showError('Please enter a valid email address');
                field.focus();
                return false;
            }
            
            if (field.type === 'tel' && !this.validatePhone(field.value)) {
                this.showError('Please enter a valid phone number (07XXXXXXXX)');
                field.focus();
                return false;
            }
        }
        
        return true;
    }
    
    validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }
    
    validatePhone(phone) {
        return /^07\d{8}$/.test(phone);
    }
    
    handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file size (5MB max)
        if (file.size > 5 * 1024 * 1024) {
            this.showError('File size must be less than 5MB');
            event.target.value = '';
            return;
        }
        
        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showError('Please upload an image file');
            event.target.value = '';
            return;
        }
        
        // Show preview
        const previewId = event.target.dataset.preview;
        if (previewId) {
            const reader = new FileReader();
            reader.onload = (e) => {
                document.getElementById(previewId).src = e.target.result;
            };
            reader.readAsDataURL(file);
        }
    }
    
    loadSavedData() {
        const saved = sessionStorage.getItem('registrationData');
        if (saved) {
            try {
                this.formData = JSON.parse(saved);
                this.populateFields();
            } catch (e) {
                console.error('Error loading saved data:', e);
            }
        }
    }
    
    saveToSession() {
        sessionStorage.setItem('registrationData', JSON.stringify(this.formData));
    }
    
    populateFields() {
        Object.entries(this.formData).forEach(([name, value]) => {
            const field = document.querySelector(`[name="${name}"]`);
            if (field) field.value = value;
        });
    }
    
    showError(message) {
        const errorDiv = document.getElementById('form-error');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }
}

// Initialize on registration page
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('registration-flow')) {
        window.registrationFlow = new RegistrationFlow();
    }
});