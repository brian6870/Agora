/**
 * AGORA VOTING - DEVICE FINGERPRINTING
 * Generates unique device identifier for "One-Device-One-Vote" security
 */

(function () {
    'use strict';

    class DeviceFingerprint {
        constructor() {
            this.components = [];
            this.hash = null;
        }

        /**
         * generating fingerprint asynchronously
         */
        async get() {
            if (this.hash) return this.hash;

            try {
                const components = await this.collectComponents();
                const entropy = components.map(c => c.value).join('||');
                this.hash = await this.sha256(entropy);
                return this.hash;
            } catch (e) {
                console.error('Fingerprint generation failed:', e);
                return 'unknown-device-' + Date.now();
            }
        }

        /**
         * Collect browser characteristics
         */
        async collectComponents() {
            return [
                { key: 'userAgent', value: navigator.userAgent },
                { key: 'language', value: navigator.language },
                { key: 'colorDepth', value: screen.colorDepth },
                { key: 'pixelRatio', value: window.devicePixelRatio },
                { key: 'screenResolution', value: `${screen.width}x${screen.height}` },
                { key: 'timezoneOffset', value: new Date().getTimezoneOffset() },
                { key: 'sessionStorage', value: !!window.sessionStorage },
                { key: 'localStorage', value: !!window.localStorage },
                { key: 'platform', value: navigator.platform },
                { key: 'hardwareConcurrency', value: navigator.hardwareConcurrency || 'unknown' },
                { key: 'deviceMemory', value: navigator.deviceMemory || 'unknown' },
                // Canvas Fingerprinting (Basic)
                { key: 'canvas', value: this.getCanvasFingerprint() }
            ];
        }

        /**
         * Generate Canvas Fingerprint
         */
        getCanvasFingerprint() {
            try {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = 200;
                canvas.height = 50;

                // Text with different fonts and styles
                ctx.textBaseline = 'top';
                ctx.font = '14px "Arial"';
                ctx.textBaseline = 'alphabetic';
                ctx.fillStyle = '#f60';
                ctx.fillRect(125, 1, 62, 20);
                ctx.fillStyle = '#069';
                ctx.fillText('AgoraVoting', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('Secure', 4, 17);

                return canvas.toDataURL();
            } catch (e) {
                return 'canvas-error';
            }
        }

        /**
         * SHA-256 Hashing helper
         */
        async sha256(message) {
            const msgBuffer = new TextEncoder().encode(message);
            const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        }
    }

    // Expose globally
    window.DeviceFingerprint = new DeviceFingerprint();

})();