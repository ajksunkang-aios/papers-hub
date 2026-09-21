// Mobile sidebar drawer toggle. Wires the hamburger button to open/close the
// left navigation sidebar on narrow viewports; closes on backdrop click,
// Escape, or navigation link tap.
(function () {
  function initSidebar() {
    var sidebar = document.getElementById("app-sidebar");
    var toggle = document.querySelector(".sidebar-toggle");
    var backdrop = document.querySelector(".sidebar-backdrop");
    if (!sidebar || !toggle) return;

    function open() {
      sidebar.classList.add("is-open");
      if (backdrop) backdrop.style.display = "block";
      toggle.setAttribute("aria-expanded", "true");
    }

    function close() {
      sidebar.classList.remove("is-open");
      if (backdrop) backdrop.style.display = "none";
      toggle.setAttribute("aria-expanded", "false");
    }

    toggle.addEventListener("click", function () {
      if (sidebar.classList.contains("is-open")) close();
      else open();
    });

    if (backdrop) backdrop.addEventListener("click", close);

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && sidebar.classList.contains("is-open")) close();
    });

    // Close when a nav link is clicked (mobile).
    sidebar.addEventListener("click", function (e) {
      var link = e.target.closest(".sidebar-nav-item");
      if (link) close();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebar);
  } else {
    initSidebar();
  }
})();
