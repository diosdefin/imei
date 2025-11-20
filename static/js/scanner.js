// Сканер IMEI с подтверждением и автозаполнением
class IMEIScanner {
    constructor() {
        this.scannedIMEIs = new Set();
        this.html5Qrcode = null;
        this.isScanning = false;
        this.bootstrapModal = null;
        this.currentIMEI = null;

        this.initializeElements();
        this.initializeEventListeners();
        this.checkScannerAvailability();
    }

    initializeElements() {
        this.readerElem = document.getElementById('reader');
        this.startBtn = document.getElementById('startScanBtn');
        this.stopBtn = document.getElementById('stopScanBtn');
        this.scannedList = document.getElementById('scannedList');
        this.emptyState = document.getElementById('emptyState');
        this.statusElem = document.getElementById('scannerStatus');
        this.placeholderElem = document.getElementById('scannerPlaceholder');
        this.manualForm = document.getElementById('manualImeiForm');
        this.manualInput = document.getElementById('manualImei');

        this.modalElem = document.getElementById('deviceConfirmModal');
        this.modalForm = document.getElementById('confirmDeviceForm');
        this.modalImei = document.getElementById('modalImei');
        this.modalModel = document.getElementById('modalModel');
        this.modalStatus = document.getElementById('modalStatus');
        this.modalComment = document.getElementById('modalComment');
        this.modalError = document.getElementById('modalError');
        this.lookupStatus = document.getElementById('lookupStatus');

        if (this.modalElem && window.bootstrap) {
            this.bootstrapModal = new bootstrap.Modal(this.modalElem);
        }
    }

    initializeEventListeners() {
        this.startBtn?.addEventListener('click', () => this.startScanner());
        this.stopBtn?.addEventListener('click', () => this.stopScanner());
        this.manualForm?.addEventListener('submit', (e) => this.handleManualInput(e));
        this.modalForm?.addEventListener('submit', (e) => this.handleModalSubmit(e));
        this.modalElem?.addEventListener('hidden.bs.modal', () => {
            this.modalError.hidden = true;
            this.lookupStatus.hidden = true;
            this.modalComment.value = '';
            this.modalModel.value = '';
            this.currentIMEI = null;
        });
    }

    checkScannerAvailability() {
        if (typeof Html5Qrcode === 'undefined') {
            this.showStatus('❌ Сканер недоступен. Используйте ручной ввод IMEI ниже.', 'error');

            if (this.startBtn) {
                this.startBtn.disabled = true;
                this.startBtn.textContent = '📵 Сканер недоступен';
            }
            return false;
        }

        this.showStatus('✅ Сканер готов к работе. Нажмите "Начать сканирование".', 'success');
        return true;
    }

    async startScanner() {
        if (this.isScanning) {
            this.showStatus('⚠️ Сканер уже запущен', 'warning');
            return;
        }

        if (typeof Html5Qrcode === 'undefined') {
            this.showStatus('❌ Библиотека сканера не загружена', 'error');
            return;
        }

        try {
            this.showStatus('🔄 Запуск сканера...', 'info');
            this.html5Qrcode = new Html5Qrcode('reader');

            const cameras = await Html5Qrcode.getCameras();
            if (cameras.length === 0) {
                this.showStatus('❌ Камеры не найдены. Проверьте разрешения браузера.', 'error');
                return;
            }

            if (this.placeholderElem) {
                this.placeholderElem.style.display = 'none';
            }

            await this.html5Qrcode.start(
                cameras[0].id,
                { fps: 10, qrbox: { width: 250, height: 250 } },
                (decodedText) => this.onScanSuccess(decodedText),
                () => {}
            );

            this.isScanning = true;
            this.updateUI();
            this.showStatus('✅ Сканер активен! Наведите на QR-код с IMEI.', 'success');
        } catch (error) {
            console.error('Ошибка запуска сканера:', error);
            this.showStatus(`❌ Ошибка: ${error.message}`, 'error');
            this.resetScanner();
        }
    }

    async stopScanner() {
        if (!this.isScanning || !this.html5Qrcode) return;

        try {
            await this.html5Qrcode.stop();
            this.resetScanner();
            this.showStatus('⏹️ Сканер остановлен', 'info');

            if (this.placeholderElem) {
                this.placeholderElem.style.display = 'block';
            }
        } catch (error) {
            console.error('Ошибка остановки:', error);
            this.showStatus('❌ Ошибка при остановке сканера', 'error');
        }
    }

    resetScanner() {
        if (this.html5Qrcode) {
            this.html5Qrcode.clear();
            this.html5Qrcode = null;
        }
        this.isScanning = false;
        this.updateUI();
    }

    onScanSuccess(decodedText) {
        const cleanIMEI = decodedText.replace(/\D/g, '');

        if (cleanIMEI.length === 15) {
            this.processScannedIMEI(cleanIMEI);
        } else if (cleanIMEI.length > 15) {
            this.processScannedIMEI(cleanIMEI.substring(0, 15));
        } else {
            this.showStatus(`⚠️ Неверный IMEI: "${decodedText}". Нужно 15 цифр.`, 'warning');
        }
    }

    handleManualInput(event) {
        event.preventDefault();
        const imei = this.manualInput.value.trim();

        if (imei.length !== 15 || !/^\d+$/.test(imei)) {
            this.showStatus('❌ IMEI должен содержать ровно 15 цифр', 'error');
            return;
        }

        this.processScannedIMEI(imei);
        this.manualInput.value = '';
    }

    async processScannedIMEI(imei) {
        if (this.scannedIMEIs.has(imei)) {
            this.showStatus(`⚠️ IMEI ${imei} уже был добавлен`, 'warning');
            return;
        }

        this.currentIMEI = imei;
        this.modalImei.value = imei;
        this.modalModel.value = '';
        if (this.modalStatus) {
            this.modalStatus.selectedIndex = 0;
        }
        this.modalComment.value = '';
        this.modalError.hidden = true;
        this.lookupStatus.hidden = true;

        if (this.bootstrapModal) {
            this.bootstrapModal.show();
        }

        this.lookupModelByImei(imei);
    }

    async lookupModelByImei(imei) {
        if (!window.ImeiLookup || !window.SCANNER_ENDPOINTS) return;

        this.setLookupMessage('⏳ Получаем модель телефона...', 'info');

        try {
            const data = await window.ImeiLookup.lookup(imei, window.SCANNER_ENDPOINTS.lookup);
            if (data.formatted_name) {
                this.modalModel.value = data.formatted_name;
                this.setLookupMessage('✅ Модель подставлена автоматически.', 'success');
            } else {
                this.setLookupMessage('ℹ️ Модель не найдена, введите вручную.', 'warning');
            }
        } catch (error) {
            const message = error.message || 'Не удалось получить модель. Введите вручную.';
            const tone = error.rateLimited ? 'warning' : 'danger';
            this.setLookupMessage(message, tone);
        }
    }

    setLookupMessage(message, tone = 'info') {
        if (!this.lookupStatus) return;
        const classes = {
            info: 'alert-info',
            success: 'alert-success',
            warning: 'alert-warning',
            danger: 'alert-danger'
        };
        this.lookupStatus.className = `alert ${classes[tone] || classes.info} small`;
        this.lookupStatus.textContent = message;
        this.lookupStatus.hidden = false;
    }

    async handleModalSubmit(event) {
        event.preventDefault();
        if (!this.currentIMEI) return;

        const payload = {
            imei: this.currentIMEI,
            model_name: this.modalModel.value.trim(),
            status: this.modalStatus.value,
            comment: this.modalComment.value.trim()
        };

        try {
            const response = await this.addToDatabase(payload);
            if (!response.success) {
                throw new Error(response.error || 'Не удалось сохранить устройство');
            }
            this.scannedIMEIs.add(this.currentIMEI);
            this.flashScreen();
            this.addToScannedList(this.currentIMEI, response.model_name);
            this.showStatus(`✅ Устройство ${this.currentIMEI} успешно добавлено!`, 'success');
            this.bootstrapModal?.hide();
        } catch (error) {
            console.error('Ошибка добавления:', error);
            this.modalError.textContent = error.message || 'Ошибка при добавлении устройства';
            this.modalError.hidden = false;
        }
    }

    async addToDatabase(payload) {
        const csrfToken = this.getCSRFToken();
        const response = await fetch(window.SCANNER_ENDPOINTS.add, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(data.error || 'Не удалось сохранить устройство');
            error.rateLimited = data.rate_limited;
            throw error;
        }
        return data;
    }

    addToScannedList(imei, modelName = '') {
        if (this.emptyState && this.emptyState.parentNode) {
            this.emptyState.remove();
        }

        const itemDiv = document.createElement('div');
        itemDiv.className = 'scanned-item border rounded p-3 mb-2 bg-light';
        itemDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <div class="d-flex align-items-center mb-1">
                        <span class="badge bg-primary me-2">IMEI</span>
                        <code class="fs-6">${imei}</code>
                    </div>
                    <div class="text-muted small">${modelName || 'Модель не указана'}</div>
                </div>
                <button class="btn btn-outline-danger btn-sm remove-btn" title="Удалить из списка">
                    🗑️
                </button>
            </div>
        `;

        itemDiv.querySelector('.remove-btn').addEventListener('click', () => {
            this.scannedIMEIs.delete(imei);
            itemDiv.remove();

            if (this.scannedList.children.length === 0 && this.emptyState) {
                this.scannedList.appendChild(this.emptyState);
            }
        });

        this.scannedList.prepend(itemDiv);
    }

    updateUI() {
        if (this.startBtn) {
            this.startBtn.disabled = this.isScanning;
        }
        if (this.stopBtn) {
            this.stopBtn.disabled = !this.isScanning;
        }
    }

    showStatus(message, type = 'info') {
        if (!this.statusElem) return;

        const alertClass = {
            error: 'danger',
            success: 'success',
            warning: 'warning',
            info: 'info'
        }[type] || 'info';

        this.statusElem.innerHTML = `
            <div class="alert alert-${alertClass} alert-dismissible fade show mb-0">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    }

    flashScreen() {
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(40, 167, 69, 0.3);
            z-index: 9999;
            pointer-events: none;
            animation: flashAnimation 0.3s ease-out;
        `;

        document.body.appendChild(flash);
        setTimeout(() => flash.remove(), 300);
    }

    getCSRFToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) return csrfInput.value;

        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith('csrftoken=')) {
                return cookie.substring('csrftoken='.length);
            }
        }
        return '';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.imeiScanner = new IMEIScanner();
});