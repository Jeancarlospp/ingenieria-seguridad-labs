const passwordToggle = document.querySelector(".password-toggle");

if (passwordToggle) {
  const passwordInput = document.getElementById(
    passwordToggle.getAttribute("aria-controls")
  );

  passwordToggle.addEventListener("click", () => {
    const showing = passwordInput.type === "password";

    passwordInput.type = showing ? "text" : "password";
    passwordToggle.textContent = showing ? "Ocultar" : "Mostrar";
    passwordToggle.setAttribute("aria-pressed", String(showing));
  });
}

const menuButton = document.querySelector(".menu-button");
const sidebar = document.querySelector(".sidebar");

function closeMenu() {
  if (!menuButton || !sidebar) return;

  sidebar.classList.remove("is-open");
  menuButton.setAttribute("aria-expanded", "false");
}

if (menuButton && sidebar) {
  menuButton.addEventListener("click", () => {
    const open = !sidebar.classList.contains("is-open");

    sidebar.classList.toggle("is-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
      menuButton.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (
      !sidebar.contains(event.target) &&
      !menuButton.contains(event.target)
    ) {
      closeMenu();
    }
  });
}