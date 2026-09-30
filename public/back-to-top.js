(function () {
  function init() {
    if (document.getElementById("back-to-top")) return;

    const btn = document.createElement("button");
    btn.id = "back-to-top";
    btn.type = "button";
    btn.className = "back-to-top";
    btn.setAttribute("aria-label", "Back to top");
    btn.hidden = true;
    btn.innerHTML =
      '<svg class="back-to-top-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" d="M12 4l-7 7h4v9h6v-9h4z"/></svg>';

    document.body.appendChild(btn);

    const showAfter = 320;
    const onScroll = () => {
      btn.hidden = window.scrollY < showAfter;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    btn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
