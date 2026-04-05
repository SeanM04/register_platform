const getFullscreenElement = () => (
    document.fullscreenElement
    || document.webkitFullscreenElement
    || null
);

const requestElementFullscreen = (element) => {
    if (element.requestFullscreen) {
        return element.requestFullscreen();
    }

    if (element.webkitRequestFullscreen) {
        element.webkitRequestFullscreen();
    }

    return Promise.resolve();
};

const exitActiveFullscreen = () => {
    if (document.exitFullscreen) {
        return document.exitFullscreen();
    }

    if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
    }

    return Promise.resolve();
};

export const initialiseFullscreenControls = (buttons, onResize) => {
    if (!buttons.length) {
        return;
    }

    const fullscreenSupported = Boolean(
        document.fullscreenEnabled
        || document.webkitFullscreenEnabled
        || document.documentElement.requestFullscreen
        || document.documentElement.webkitRequestFullscreen
    );

    const syncFullscreenButtons = () => {
        const activeCard = getFullscreenElement();

        buttons.forEach((button) => {
            const card = button.closest(".level-insight-card");
            const chartTitle = button.dataset.chartTitle || "chart";
            const isActive = Boolean(card && activeCard === card);

            if (card) {
                card.classList.toggle("is-fullscreen", isActive);
            }

            button.textContent = isActive ? "Exit full screen" : "Full screen";
            button.setAttribute("aria-pressed", String(isActive));
            button.setAttribute(
                "aria-label",
                `${isActive ? "Exit" : "View"} ${chartTitle} ${isActive ? "from" : "in"} full screen`,
            );
        });

        window.requestAnimationFrame(() => {
            onResize();
        });
    };

    if (!fullscreenSupported) {
        buttons.forEach((button) => {
            button.hidden = true;
        });
        return;
    }

    buttons.forEach((button) => {
        button.addEventListener("click", async () => {
            const card = button.closest(".level-insight-card");
            if (!card) {
                return;
            }

            try {
                if (getFullscreenElement() === card) {
                    await exitActiveFullscreen();
                } else {
                    await requestElementFullscreen(card);
                }
            } catch (error) {
                return;
            }

            syncFullscreenButtons();
        });
    });

    document.addEventListener("fullscreenchange", syncFullscreenButtons);
    document.addEventListener("webkitfullscreenchange", syncFullscreenButtons);
    syncFullscreenButtons();
};
