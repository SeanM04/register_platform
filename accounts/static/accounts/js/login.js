const loginForm = document.getElementById("login-form");
const feedback = document.getElementById("auth-feedback");
const passwordInput = document.getElementById("login-password");
const passwordToggle = document.getElementById("password-toggle");

if (passwordInput && passwordToggle) {
    passwordToggle.addEventListener("click", () => {
        const isVisible = passwordInput.type === "text";
        passwordInput.type = isVisible ? "password" : "text";
        passwordToggle.classList.toggle("is-visible", !isVisible);
        passwordToggle.setAttribute("aria-pressed", String(!isVisible));
        passwordToggle.setAttribute("aria-label", isVisible ? "Show password" : "Hide password");
    });
}

if (loginForm && feedback) {
    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        feedback.hidden = true;
        feedback.textContent = "";

        const formData = new FormData(loginForm);
        const response = await fetch(loginForm.action, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });

        const payload = await response.json();
        if (response.ok && payload.redirect) {
            window.location.href = payload.redirect;
            return;
        }

        if (payload.lockout_info) {
            feedback.textContent = `Too many failed attempts. Try again after ${payload.lockout_info.locked_until}.`;
        } else {
            feedback.textContent = payload.error || "Unable to log in.";
        }
        feedback.hidden = false;
    });
}
