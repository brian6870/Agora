// static/js/ocr.js
// Mock OCR functionality (in production, integrate with actual OCR service)

class OCRProcessor {
    constructor() {
        this.API_ENDPOINT = '/api/ocr/process'; // Backend OCR endpoint
    }
    
    async processImage(imageFile) {
        // Show loading state
        this.showLoading();
        
        try {
            const formData = new FormData();
            formData.append('image', imageFile);
            
            const response = await fetch(this.API_ENDPOINT, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.displayExtractedData(data.extracted);
                this.compareWithInput(data.extracted);
            } else {
                this.showError('Could not extract text from image. Please try again.');
            }
            
        } catch (error) {
            console.error('OCR error:', error);
            this.showError('OCR processing failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }
    
    displayExtractedData(data) {
        const container = document.getElementById('ocr-results');
        if (!container) return;
        
        container.innerHTML = `
            <div class="card" style="margin-top: 16px;">
                <h4>Extracted Information</h4>
                <div style="margin-top: 12px;">
                    <div><strong>Name:</strong> ${data.name || 'Not detected'}</div>
                    <div><strong>ID Number:</strong> ${data.id_number || 'Not detected'}</div>
                    <div><strong>Date of Birth:</strong> ${data.dob || 'Not detected'}</div>
                </div>
            </div>
        `;
    }
    
    compareWithInput(extracted) {
        const nameInput = document.querySelector('input[name="full_name"]');
        const idInput = document.querySelector('input[name="id_number"]');
        
        if (nameInput && extracted.name) {
            const similarity = this.calculateSimilarity(
                nameInput.value.toLowerCase(),
                extracted.name.toLowerCase()
            );
            
            if (similarity < 0.8) {
                this.showWarning('Name on ID does not match entered name');
            }
        }
        
        if (idInput && extracted.id_number) {
            if (idInput.value !== extracted.id_number) {
                this.showWarning('ID number on ID does not match entered ID');
            }
        }
    }
    
    calculateSimilarity(str1, str2) {
        // Simple similarity check (in production, use proper string matching)
        if (str1 === str2) return 1;
        if (str1.includes(str2) || str2.includes(str1)) return 0.9;
        return 0.5;
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
    
    showLoading() {
        const loader = document.getElementById('ocr-loading');
        if (loader) loader.style.display = 'block';
    }
    
    hideLoading() {
        const loader = document.getElementById('ocr-loading');
        if (loader) loader.style.display = 'none';
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-error';
        errorDiv.textContent = message;
        document.getElementById('ocr-results')?.appendChild(errorDiv);
    }
    
    showWarning(message) {
        const warningDiv = document.createElement('div');
        warningDiv.className = 'alert alert-warning';
        warningDiv.innerHTML = `<strong>Warning:</strong> ${message}`;
        document.getElementById('ocr-results')?.appendChild(warningDiv);
    }
}