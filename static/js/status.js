const getCookie = (name) => {
    if (!document.cookie) return null;
    const match = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null;
};

const showToast = (message, isError = false) => {
    const alert = document.createElement('div');
    alert.className = `alert alert-${isError ? 'danger' : 'success'} position-fixed top-0 end-0 m-3`;
    alert.role = 'alert';
    alert.textContent = message;
    document.body.appendChild(alert);
    setTimeout(() => alert.remove(), 3000);
};

document.addEventListener('focusin', (event) => {
    if (event.target.classList.contains('status-selector')) {
        event.target.dataset.originalValue = event.target.value;
    }
});

document.addEventListener('change', (event) => {
    if (!event.target.classList.contains('status-selector')) return;
    const select = event.target;
    const previousValue = select.dataset.originalValue || select.value;
    const url = select.dataset.url;
    const value = select.value;
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken') || '',
        },
        body: new URLSearchParams({status: value}),
    })
        .then((response) => {
            if (!response.ok) throw response;
            return response.json();
        })
        .then((data) => {
            if (data.success) {
                select.dataset.originalValue = value;
                showToast('Статус обновлен');
            }
        })
        .catch(async (error) => {
            select.value = previousValue;
            showToast('Ошибка при обновлении статуса', true);
            if (error.json) {
                const info = await error.json();
                console.error(info);
            }
        });
});

