/**
 * Load KPI groups independently so nested metric widgets do not duplicate requests.
 */
const metricGroups = Array.from(document.querySelectorAll("[data-metrics-url]")).filter((group) => {
    const parentMetricGroup = group.parentElement?.closest("[data-metrics-url]");
    return !parentMetricGroup;
});

metricGroups.forEach((group) => {
    const endpoint = group.dataset.metricsUrl;
    if (!endpoint) {
        return;
    }

    const metricValues = group.querySelectorAll("[data-metric-value]");
    if (!metricValues.length) {
        return;
    }
    const requestUrl = new URL(endpoint, window.location.origin);
    const currentUrl = new URL(window.location.href);

    currentUrl.searchParams.forEach((value, key) => {
        requestUrl.searchParams.set(key, value);
    });

    fetch(requestUrl, {
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
        },
    })
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Metric request failed with status ${response.status}`);
            }
            return response.json();
        })
        .then((payload) => {
            const metrics = payload.metrics || {};

            metricValues.forEach((node) => {
                const metricKey = node.dataset.metricKey;
                if (Object.prototype.hasOwnProperty.call(metrics, metricKey)) {
                    node.textContent = metrics[metricKey];
                }
                node.classList.remove("is-loading");
                node.classList.add("is-loaded");
            });
        })
        .catch(() => {
            metricValues.forEach((node) => {
                node.textContent = "Unavailable";
                node.classList.remove("is-loading");
                node.classList.add("is-error");
            });
        });
});
