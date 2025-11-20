class QrScannerManager {
    constructor() {
        this.html5Qrcode = null;
        this.isScanning = false;
        this.lastScannedImei = null;
    }

    initScanner() {
        const scannerContainer = document.getElementById('reader');
        const scannerPlaceholder = document.getElementById('scannerPlaceholder');
        const startScanBtn = document.getElementById('startScanBtn');
        const stopScanBtn = document.getElementById('stopScanBtn');
        const scannerStatus = document.getElementById('scannerStatus');
        const manualImeiForm = document.getElementById('manualImeiForm');
        const manualImeiInput = document.getElementById('manualImei');
        const scannedList = document.getElementById('scannedList');
        const emptyState = document.getElementById('emptyState');

        this.html5Qrcode = new Html5Qrcode("reader");

        startScanBtn.addEventListener('click', () => {
            this.startScanning(scannerContainer, scannerPlaceholder, startScanBtn, 
                stopScanBtn, scannerStatus);
        });

        stopScanBtn.addEventListener('click', () => {
            this.stopScanning(startScanBtn, stopScanBtn, scannerStatus);
        });

        manualImeiForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleManualImei(manualImeiInput.value, scannedList, emptyState);
        });
    }

    async startScanning(container, placeholder, startBtn, stopBtn, status) {
        try {
            const cameras = await Html5Qrcode.getCameras();
            if (cameras && cameras.length > 0) {
                const cameraId = cameras[0].id;
                
                // Скрываем плейсхолдер и показываем сканер
                placeholder.style.display = 'none';
                container.style.padding = '0';
                
                await this.html5Qrcode.start(
                    cameraId,
                    {
                        fps: 10,
                        qrbox: { width: 250, height: 150 },
                        aspectRatio: 1.0
                    },
                    (decodedText) => {
                        this.handleScannedCode(decodedText, status);
                    },
                    (errorMessage) => {
                        // Игнорируем ошибки сканирования, продолжаем сканировать
                    }
                );

                this.isScanning = true;
                startBtn.disabled = true;
                stopBtn.disabled = false;
                status.innerHTML = '<div class="alert alert-success">📷 Сканирование активно</div>';
                
            } else {
                throw new Error('Камеры не найдены');
            }
        } catch (error) {
            console.error('Ошибка запуска сканера:', error);
            status.innerHTML = `<div class="alert alert-danger">❌ Ошибка: ${error.message}</div>`;
        }
    }

    async stopScanning(startBtn, stopBtn, status) {
        if (this.html5Qrcode && this.isScanning) {
            try {
                await this.html5Qrcode.stop();
                this.isScanning = false;
                startBtn.disabled = false;
                stopBtn.disabled = true;
                status.innerHTML = '<div class="alert alert-info">⏸️ Сканирование остановлено</div>';
            } catch (error) {
                console.error('Ошибка остановки сканера:', error);
            }
        }
    }

    handleScannedCode(decodedText, status) {
        // Проверяем, что отсканирован IMEI (15 цифр)
        const imei = decodedText.trim();
        
        if (/^\d{15}$/.test(imei)) {
            if (this.lastScannedImei !== imei) {
                this.lastScannedImei = imei;
                this.addDeviceFromScan(imei, status);
            }
        } else {
            status.innerHTML = `<div class="alert alert-warning">⚠️ Не IMEI: ${imei}</div>`;
        }
    }

    handleManualImei(imei, scannedList, emptyState) {
        imei = imei.trim();
        
        if (/^\d{15}$/.test(imei)) {
            this.addDeviceFromScan(imei);
            document.getElementById('manualImei').value = '';
        } else {
            alert('IMEI должен содержать 15 цифр');
        }
    }

    addDeviceFromScan(imei, status = null) {
        const csrfToken = this.getCsrfToken();
        
        fetch('/devices/add-from-scan/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ imei: imei })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (status) {
                    status.innerHTML = `<div class="alert alert-success">✅ Устройство добавлено: ${imei}</div>`;
                }
                this.addToScannedList(imei, true, 'Успешно добавлено');
                
                // Автоматическое обновление через 2 секунды
                setTimeout(() => {
                    window.location.href = '/devices/';
                }, 2000);
                
            } else {
                if (status) {
                    status.innerHTML = `<div class="alert alert-warning">⚠️ ${data.error}</div>`;
                }
                this.addToScannedList(imei, false, data.error);
            }
        })
        .catch(error => {
            console.error('Ошибка:', error);
            if (status) {
                status.innerHTML = `<div class="alert alert-danger">❌ Ошибка сети</div>`;
            }
            this.addToScannedList(imei, false, 'Ошибка сети');
        });
    }

    addToScannedList(imei, success, message) {
        const scannedList = document.getElementById('scannedList');
        const emptyState = document.getElementById('emptyState');
        
        // Скрываем пустое состояние
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        
        const item = document.createElement('div');
        item.className = `scanned-item alert ${success ? 'alert-success' : 'alert-warning'} mb-2`;
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>${imei}</strong>
                    <small class="d-block text-muted">${new Date().toLocaleTimeString()}</small>
                </div>
                <div>
                    ${success ? '✅' : '⚠️'} ${message}
                </div>
            </div>
        `;
        
        scannedList.insertBefore(item, scannedList.firstChild);
        
        // Ограничиваем список 10 элементами
        const items = scannedList.getElementsByClassName('scanned-item');
        if (items.length > 10) {
            scannedList.removeChild(items[items.length - 1]);
        }
    }

    getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const scannerManager = new QrScannerManager();
    scannerManager.initScanner();
});