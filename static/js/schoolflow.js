document.addEventListener("DOMContentLoaded", function () {
  const body = document.body;
  const sidebar = document.querySelector(".sidebar");
  const overlay = document.querySelector(".body-overlay");
  const toggleButtons = document.querySelectorAll(".shell-sidebar-toggle");
  const mobileButtons = document.querySelectorAll(".shell-sidebar-mobile-toggle");
  const closeButtons = document.querySelectorAll(".shell-sidebar-close-btn");
  const sidebarDropdownButtons = document.querySelectorAll(".sidebar-dropdown-toggle");

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("sidebar-open");
    body.classList.remove("overlay-active");
  }

  toggleButtons.forEach((button) => {
    button.addEventListener("click", function () {
      if (window.innerWidth >= 1200) {
        body.classList.toggle("sidebar-collapsed");
      } else {
        if (sidebar) sidebar.classList.toggle("sidebar-open");
        body.classList.toggle("overlay-active");
      }
    });
  });

  mobileButtons.forEach((button) => {
    button.addEventListener("click", function () {
      if (sidebar) sidebar.classList.add("sidebar-open");
      body.classList.add("overlay-active");
    });
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", closeSidebar);
  });

  document.querySelectorAll(".sidebar-item.has-submenu").forEach((item) => {
    const submenu = item.querySelector(".sidebar-subitem");
    const toggle = item.querySelector(".sidebar-dropdown-toggle");
    const hasActiveChild = Boolean(item.querySelector(".sidebar-subitem .active-page"));
    if (hasActiveChild) item.classList.add("submenu-open");
    if (toggle) {
      toggle.setAttribute("aria-expanded", item.classList.contains("submenu-open") ? "true" : "false");
    }
    if (submenu) {
      submenu.setAttribute("aria-hidden", item.classList.contains("submenu-open") ? "false" : "true");
    }
  });

  sidebarDropdownButtons.forEach((button) => {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      const item = button.closest(".sidebar-item.has-submenu");
      if (!item) return;
      const willOpen = !item.classList.contains("submenu-open");

      document.querySelectorAll(".sidebar-item.has-submenu.submenu-open").forEach((openItem) => {
        if (openItem === item) return;
        openItem.classList.remove("submenu-open");
        openItem.querySelector(".sidebar-dropdown-toggle")?.setAttribute("aria-expanded", "false");
        openItem.querySelector(".sidebar-subitem")?.setAttribute("aria-hidden", "true");
      });

      item.classList.toggle("submenu-open", willOpen);
      button.setAttribute("aria-expanded", willOpen ? "true" : "false");
      item.querySelector(".sidebar-subitem")?.setAttribute("aria-hidden", willOpen ? "false" : "true");
    });
  });

  if (overlay) {
    overlay.addEventListener("click", closeSidebar);
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeSidebar();
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth >= 1200) {
      closeSidebar();
    } else {
      body.classList.remove("sidebar-collapsed");
    }
  });

  document.querySelectorAll("[data-sf-width]").forEach((el) => {
    const raw = el.getAttribute("data-sf-width") || "";
    const value = Number(String(raw).replace("%", "").trim());
    if (!Number.isFinite(value)) return;
    const safe = Math.max(0, Math.min(100, value));
    el.style.width = `${safe}%`;
  });

  document.addEventListener("shown.bs.dropdown", function (event) {
    const menu = event.target?.querySelector?.(".dropdown-menu");
    if (!menu) return;
    const firstItem = menu.querySelector(".dropdown-item:not(.disabled):not([aria-disabled='true'])");
    firstItem?.focus?.();
  });
});
