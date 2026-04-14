const RISK_CHART_MODAL_ID = "risk-chart-modal";
let activeChartModal = null;

const setButtonState = (button, isOpen) => {
    if (!button) {
        return;
    }

    const chartTitle = button.dataset.chartTitle || "chart";
    button.textContent = isOpen ? "Close view" : "Full screen";
    button.setAttribute("aria-pressed", String(isOpen));
    button.setAttribute(
        "aria-label",
        `${isOpen ? "Close" : "View"} ${chartTitle} ${isOpen ? "dialog" : "in dialog"}`,
    );
};

const closeActiveChartModal = () => {
    if (!activeChartModal) {
        return;
    }

    const {
        modal,
        placeholder,
        card,
        originalParent,
        button,
        handleEscapeKey,
        onResize,
        lastFocusedElement,
    } = activeChartModal;

    if (originalParent && placeholder?.parentNode === originalParent) {
        originalParent.insertBefore(card, placeholder.nextSibling);
        placeholder.remove();
    }

    card.classList.remove("is-fullscreen");
    setButtonState(button, false);

    if (modal) {
        modal.remove();
    }

    document.body.classList.remove("has-risk-chart-modal");
    document.removeEventListener("keydown", handleEscapeKey);

    window.requestAnimationFrame(() => {
        onResize();
    });

    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        lastFocusedElement.focus();
    } else if (button && typeof button.focus === "function") {
        button.focus();
    }

    activeChartModal = null;
};

export const initialiseFullscreenControls = (buttons, onResize) => {
    if (!buttons.length) {
        return;
    }

    buttons.forEach((button) => {
        setButtonState(button, false);

        button.addEventListener("click", () => {
            const card = button.closest(".risk-insight-card");
            if (!card) {
                return;
            }

            if (activeChartModal?.card === card) {
                closeActiveChartModal();
                return;
            }

            closeActiveChartModal();

            const originalParent = card.parentNode;
            if (!originalParent) {
                return;
            }

            const placeholder = document.createElement("div");
            placeholder.hidden = true;
            originalParent.insertBefore(placeholder, card);

            const modal = document.createElement("div");
            modal.id = RISK_CHART_MODAL_ID;
            modal.className = "risk-chart-modal";
            modal.innerHTML = `
                <div class="risk-chart-dialog" role="dialog" aria-modal="true" aria-labelledby="risk-chart-modal-title" tabindex="-1">
                    <div class="risk-chart-dialog-header">
                        <div class="risk-chart-dialog-heading">
                            <h2 class="risk-chart-dialog-title" id="risk-chart-modal-title">${button.dataset.chartTitle || "Chart view"}</h2>
                            <p class="risk-chart-dialog-subtitle">Focused chart view for closer inspection without leaving the risk analysis page.</p>
                        </div>
                        <button class="risk-chart-dialog-close" type="button" aria-label="Close chart dialog">Close</button>
                    </div>
                    <div class="risk-chart-dialog-body"></div>
                </div>
            `.trim();

            const dialog = modal.querySelector(".risk-chart-dialog");
            const dialogBody = modal.querySelector(".risk-chart-dialog-body");
            const closeButton = modal.querySelector(".risk-chart-dialog-close");

            if (!dialog || !dialogBody || !closeButton) {
                placeholder.remove();
                return;
            }

            const handleEscapeKey = (event) => {
                if (event.key === "Escape") {
                    closeActiveChartModal();
                }
            };

            modal.addEventListener("click", (event) => {
                if (event.target === modal) {
                    closeActiveChartModal();
                }
            });
            closeButton.addEventListener("click", () => {
                closeActiveChartModal();
            });

            dialogBody.appendChild(card);
            card.classList.add("is-fullscreen");
            setButtonState(button, true);

            document.body.appendChild(modal);
            document.body.classList.add("has-risk-chart-modal");
            document.addEventListener("keydown", handleEscapeKey);

            activeChartModal = {
                modal,
                placeholder,
                card,
                originalParent,
                button,
                handleEscapeKey,
                onResize,
                lastFocusedElement: document.activeElement,
            };

            if (typeof dialog.focus === "function") {
                dialog.focus();
            }

            window.requestAnimationFrame(() => {
                onResize();
            });
        });
    });
};
