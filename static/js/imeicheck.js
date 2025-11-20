(() => {
    const cache = new Map();

    async function lookup(imei, endpoint) {
        const normalized = (imei || '').trim();
        if (normalized.length !== 15) {
            throw new Error('IMEI должен содержать 15 цифр');
        }

        if (cache.has(normalized)) {
            return cache.get(normalized);
        }

        const url = new URL(endpoint, window.location.origin);
        url.searchParams.set('imei', normalized);

        const response = await fetch(url);
        const payload = await response.json();

        if (!response.ok || !payload.success) {
            const error = new Error(payload.error || 'IMEI не найден');
            error.rateLimited = payload.rate_limited;
            throw error;
        }

        cache.set(normalized, payload);
        return payload;
    }

    window.ImeiLookup = {
        lookup,
        clearCache: () => cache.clear()
    };
})();

