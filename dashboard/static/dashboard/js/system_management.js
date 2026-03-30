const systemModal = document.getElementById("add-user-modal");

if (systemModal) {
    const openButtons = document.querySelectorAll('[data-modal-open="add-user-modal"]');
    const closeButtons = systemModal.querySelectorAll("[data-modal-close]");
    const firstFocusable = systemModal.querySelector("input, select, textarea, button");

    const openModal = () => {
        systemModal.hidden = false;
        systemModal.classList.add("is-open");
        document.body.classList.add("is-modal-open");
        if (firstFocusable) {
            window.setTimeout(() => firstFocusable.focus(), 20);
        }
    };

    const closeModal = () => {
        systemModal.classList.remove("is-open");
        systemModal.hidden = true;
        document.body.classList.remove("is-modal-open");
    };

    openButtons.forEach((button) => {
        button.addEventListener("click", openModal);
    });

    closeButtons.forEach((button) => {
        button.addEventListener("click", closeModal);
    });

    systemModal.addEventListener("click", (event) => {
        if (event.target === systemModal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !systemModal.hidden) {
            closeModal();
        }
    });

    if (!systemModal.hidden) {
        document.body.classList.add("is-modal-open");
    }
}
