/* Prairie Shine Window Cleaning — interactions (vanilla, no deps) */
(function () {
  "use strict";

  /* Current year in footers */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });

  /* Sticky-nav shadow on scroll */
  var header = document.querySelector(".site-header");
  if (header) {
    var onScroll = function () {
      header.classList.toggle("scrolled", window.scrollY > 12);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* Mobile menu toggle */
  var toggle = document.querySelector(".nav__toggle");
  var menu = document.querySelector(".mobile-menu");
  if (toggle && menu) {
    var setMenu = function (open) {
      document.body.classList.toggle("menu-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      document.body.style.overflow = open ? "hidden" : "";
    };
    toggle.addEventListener("click", function () {
      setMenu(!document.body.classList.contains("menu-open"));
    });
    menu.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { setMenu(false); });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setMenu(false);
    });
  }

  /* Scroll reveal via IntersectionObserver (GPU-safe) */
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  /* Quote / contact form — client-side validation + honeypot spam trap.
     NOTE: a static site cannot email on its own. Point action= at a form
     backend (Formspree / Netlify Forms / Web3Forms) — see README. */
  document.querySelectorAll("form[data-quote]").forEach(function (form) {
    var status = form.querySelector(".form-status");
    form.addEventListener("submit", function (e) {
      // Honeypot: real users never fill this hidden field.
      var hp = form.querySelector('input[name="company_website"]');
      if (hp && hp.value.trim() !== "") { e.preventDefault(); return; }

      var name = form.querySelector('[name="name"]');
      var email = form.querySelector('[name="email"]');
      var emailOk = email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim());

      if (!name || !name.value.trim() || !emailOk) {
        e.preventDefault();
        if (status) {
          status.className = "form-status err";
          status.textContent = "Please add your name and a valid email so we can send your quote.";
        }
        return;
      }

      // If no real backend is wired yet, don't fake a network success.
      var action = (form.getAttribute("action") || "").trim();
      if (!action || action.indexOf("REPLACE") !== -1 || action === "#") {
        e.preventDefault();
        if (status) {
          status.className = "form-status ok";
          status.textContent = "Thanks " + name.value.trim().split(" ")[0] +
            "! This demo form isn't connected yet — call or text us and we'll get you a same-day quote.";
        }
        form.reset();
      }
      // Otherwise the browser submits to the configured backend normally.
    });
  });

  /* Cookie consent (meaningful consent; non-essential off by default) */
  var KEY = "ps-cookie-consent";
  var banner = document.querySelector(".cookie");
  if (banner) {
    var stored;
    try { stored = localStorage.getItem(KEY); } catch (err) { stored = "seen"; }
    if (!stored) {
      setTimeout(function () { banner.classList.add("show"); }, 900);
    }
    banner.querySelectorAll("[data-consent]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        try { localStorage.setItem(KEY, btn.getAttribute("data-consent")); } catch (err) {}
        banner.classList.remove("show");
        // When "accept" is chosen you would initialise analytics here.
      });
    });
  }
})();
