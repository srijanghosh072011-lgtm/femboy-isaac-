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

  /* Instant-estimate quiz.
     ===== EDIT THESE TWO NUMBERS to change the price band =====
     A small job lands near MIN, the biggest single-storey job near MAX.
     "Inside & out" multiplies by the data-mult on that option (1.3 by default). */
  var CALC_MIN = 50;   // $ for the smallest job (small condo, few windows, outside only)
  var CALC_MAX = 115;  // $ for the biggest single-storey job, outside only (× 1.3 for inside & out ≈ $150)

  document.querySelectorAll("[data-calc]").forEach(function (calc) {
    var steps = Array.prototype.slice.call(calc.querySelectorAll(".calc__step"));
    var result = calc.querySelector("[data-result]");
    var fill = calc.querySelector("[data-fill]");
    var backBtn = calc.querySelector("[data-back]");
    var nav = calc.querySelector(".calc__nav");
    var answers = {};
    var idx = 0;

    function round5(n) { n = Math.round(n / 5) * 5; return Math.max(50, Math.min(160, n)); }

    function showStep(i) {
      idx = i;
      steps.forEach(function (s, n) { s.classList.toggle("active", n === i); });
      result.classList.remove("active");
      nav.style.display = "";
      backBtn.hidden = i === 0;
      fill.style.width = ((i + 1) / (steps.length + 1)) * 100 + "%";
    }

    function showResult() {
      steps.forEach(function (s) { s.classList.remove("active"); });
      result.classList.add("active");
      nav.style.display = "none";
      fill.style.width = "100%";
    }

    function finish() {
      var size = parseFloat(answers.size || 0);
      var win = parseFloat(answers.windows || 0);
      var mult = parseFloat(answers.io || 1);
      var score = size * 0.6 + win * 0.4;                 // 0..1, home size weighted a bit heavier
      var est = round5((CALC_MIN + score * (CALC_MAX - CALC_MIN)) * mult);
      calc.querySelector("[data-rlabel]").textContent = "Your estimate";
      calc.querySelector("[data-amount]").innerHTML = '<span class="grad-text">about $' + est + "</span>";
      calc.querySelector("[data-rnote]").textContent =
        "A ballpark for a single-storey home — I'll confirm the exact price before I start. No surprises.";
      var chips = calc.querySelector("[data-summary]");
      chips.innerHTML = "";
      [answers.sizeLabel, answers.windowsLabel, answers.ioLabel].forEach(function (t) {
        if (t) { var e = document.createElement("span"); e.textContent = t; chips.appendChild(e); }
      });
      showResult();
    }

    function twoStorey() {
      calc.querySelector("[data-rlabel]").textContent = "Two-storey home";
      calc.querySelector("[data-amount]").innerHTML = '<span class="grad-text">Let’s talk</span>';
      calc.querySelector("[data-summary]").innerHTML = "";
      calc.querySelector("[data-rnote]").textContent =
        "I focus on single-storey homes right now, so two-storey needs a quick chat. Give me a call and we'll figure it out.";
      showResult();
    }

    steps.forEach(function (step) {
      var key = step.getAttribute("data-key");
      step.querySelectorAll(".calc__opt").forEach(function (opt) {
        opt.addEventListener("click", function () {
          step.querySelectorAll(".calc__opt").forEach(function (o) { o.classList.remove("sel"); });
          opt.classList.add("sel");
          if (opt.hasAttribute("data-flag")) { twoStorey(); return; }
          answers[key] = opt.getAttribute("data-score") || opt.getAttribute("data-mult") || "";
          answers[key + "Label"] = opt.textContent.trim();
          var next = idx + 1;
          setTimeout(function () { next < steps.length ? showStep(next) : finish(); }, 200);
        });
      });
    });

    backBtn.addEventListener("click", function () { if (idx > 0) showStep(idx - 1); });
    calc.querySelector("[data-restart]").addEventListener("click", function () {
      answers = {};
      steps.forEach(function (s) { s.querySelectorAll(".calc__opt").forEach(function (o) { o.classList.remove("sel"); }); });
      showStep(0);
    });

    showStep(0);
  });
})();
