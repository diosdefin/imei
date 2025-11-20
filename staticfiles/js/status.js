// Обработчик изменения статуса устройства
document.addEventListener('DOMContentLoaded', function() {
    const statusSelectors = document.querySelectorAll('.status-selector');
    
    statusSelectors.forEach(selector => {
        selector.addEventListener('change', function() {
            const deviceId = this.getAttribute('data-url').split('/').filter(Boolean).pop();
            const newStatus = this.value;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            fetch(`/devices/${deviceId}/status/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken
                },
                body: `status=${newStatus}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Обновляем отображение статуса
                    const badge = this.closest('td').querySelector('.badge');
                    if (badge) {
                        badge.textContent = data.status_label;
                        badge.className = `badge badge-status ${
                            data.status === 'in_stock' ? 'bg-success' :
                            data.status === 'sold' ? 'bg-primary' :
                            data.status === 'warranty' ? 'bg-info' :
                            data.status === 'trash' ? 'bg-warning' : 'bg-secondary'
                        }`;
                    }
                    
                    // Показываем уведомление
                    showMessage('Статус обновлен', 'success');
                } else {
                    showMessage('Ошибка обновления статуса', 'error');
                    this.value = this.getAttribute('data-previous-value');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Ошибка сети', 'error');
                this.value = this.getAttribute('data-previous-value');
            });
            
            // Сохраняем предыдущее значение на случай ошибки
            this.setAttribute('data-previous-value', this.value);
        });
    });
});

function showMessage(message, type) {
    // Используем существующую систему сообщений Django
    const messagesContainer = document.querySelector('.messages');
    if (messagesContainer) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        messagesContainer.appendChild(alert);
    }
}