// SeedBridge front end: Motion (motion.dev) animations per page, live progress, small helpers.
(function () {
  const M = window.Motion;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canAnimate = !!M && !reduce;
  const page = document.body.dataset.page;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const ease = [0.22, 1, 0.36, 1];

  if (canAnimate) document.documentElement.classList.add("motion-ready");

  // ---------- shared: count-ups, rings, bars
  function countUp(el, delay = 0) {
    const to = Number(el.dataset.count);
    if (!canAnimate || !Number.isFinite(to)) return;
    M.animate(0, to, { duration: 1.2, delay, ease, onUpdate: (v) => (el.textContent = Math.round(v)) });
  }
  function drawRing(wrap, delay = 0) {
    const arc = $("[data-ring-arc]", wrap);
    const target = 100 - Number(wrap.dataset.ring || 0);
    if (!arc || !canAnimate) return;
    M.animate(arc, { strokeDashoffset: [100, target] }, { duration: 1.3, delay, ease });
    $$("[data-count]", wrap).forEach((n) => countUp(n, delay));
  }
  function growBars(scope, delay = 0) {
    if (!canAnimate) return;
    $$("[data-bar]", scope).forEach((bar, i) => {
      M.animate(bar, { width: ["0%", bar.style.width] }, { duration: 0.9, delay: delay + i * 0.06, ease });
    });
  }

  // ---------- shared: reveal on scroll + staggered children
  function reveal(el) {
    if (el.dataset.revealed) return;
    el.dataset.revealed = "1";
    if (el.hasAttribute("data-stagger")) {
      const kids = [...el.children];
      M.animate(kids, { opacity: [0, 1], y: [24, 0], scale: [0.98, 1] }, { duration: 0.6, delay: M.stagger(0.08), ease });
      kids.forEach((k) => {
        $$("[data-ring]", k).forEach((r) => drawRing(r, 0.25));
      });
    } else {
      M.animate(el, { opacity: [0, 1], y: [28, 0] }, { duration: 0.7, ease });
      $$("[data-ring]", el).forEach((r) => drawRing(r, 0.15));
      growBars(el, 0.3);
      $$(".stats [data-count], [data-count]", el).forEach((n) => { if (!n.closest("[data-ring]")) countUp(n, 0.1); });
    }
  }
  if (canAnimate) {
    M.animate(".topbar", { opacity: [0, 1], y: [-16, 0] }, { duration: 0.6, ease });
    $$("[data-reveal], [data-stagger]").forEach((el) => M.inView(el, () => reveal(el), { amount: 0.15 }));
    $$("[data-pop]").forEach((el) =>
      M.animate(el, { opacity: [0, 1], y: [30, 0], scale: [0.97, 1] }, { type: "spring", stiffness: 160, damping: 20 })
    );
    $$("[data-flash]").forEach((el) => M.animate(el, { opacity: [0, 1], y: [-10, 0] }, { duration: 0.4 }));
    // gentle lift on cards
    $$("[data-lift]").forEach((card) => {
      M.hover(card, () => {
        M.animate(card, { y: -6 }, { type: "spring", stiffness: 300, damping: 22 });
        return () => M.animate(card, { y: 0 }, { type: "spring", stiffness: 300, damping: 22 });
      });
    });
    // buttons squish on press
    M.press(".btn", (el) => {
      M.animate(el, { scale: 0.96 }, { duration: 0.1 });
      return () => M.animate(el, { scale: 1 }, { type: "spring", stiffness: 500, damping: 18 });
    });
    // the colour blobs drift slowly
    $$(".backdrop i").forEach((b, i) =>
      M.animate(b, { x: [0, i % 2 ? -40 : 50, 0], y: [0, i % 2 ? 30 : -40, 0] }, { duration: 16 + i * 4, repeat: Infinity, ease: "easeInOut" })
    );
  }

  // ---------- page: home
  if (page === "home" && canAnimate) {
    const h1 = $("[data-split]");
    if (h1) {
      // split headline into words, keep the gradient span intact
      const wrapWords = (node) => {
        [...node.childNodes].forEach((child) => {
          if (child.nodeType === 3) {
            const frag = document.createDocumentFragment();
            child.textContent.split(/(\s+)/).forEach((part) => {
              if (!part) return;
              if (/^\s+$/.test(part)) frag.append(part);
              else { const s = document.createElement("span"); s.className = "word"; s.textContent = part; frag.append(s); }
            });
            child.replaceWith(frag);
          } else if (child.nodeType === 1) child.classList.add("word"); // gradient text animates as one unit
        });
      };
      wrapWords(h1);
      M.animate($$(".word", h1), { opacity: [0, 1], y: [28, 0], filter: ["blur(8px)", "blur(0px)"] }, { duration: 0.7, delay: M.stagger(0.06, { startDelay: 0.15 }), ease });
    }
    M.animate($$("[data-hero]"), { opacity: [0, 1], y: [20, 0] }, { duration: 0.7, delay: M.stagger(0.12, { startDelay: 0.45 }), ease });
    const photo = $("[data-parallax]");
    if (photo) {
      M.animate(photo, { opacity: [0, 1], scale: [1.06, 1], clipPath: ["inset(8% 8% 8% 8% round 32px)", "inset(0% 0% 0% 0% round 32px)"] }, { duration: 1.1, delay: 0.2, ease });
      M.scroll(M.animate($("img", photo), { y: [0, 60], scale: [1.04, 1.12] }, { ease: "linear" }), { target: photo, offset: ["start start", "end start"] });
    }
    $$("[data-float]").forEach((card) => {
      const i = Number(card.dataset.float);
      M.animate(card, { opacity: [0, 1], y: [30, 0], scale: [0.9, 1] }, { type: "spring", stiffness: 120, damping: 14, delay: 0.8 + i * 0.25 });
      setTimeout(() => M.animate(card, { y: [0, i % 2 ? 10 : -10, 0] }, { duration: 5 + i, repeat: Infinity, ease: "easeInOut" }), 1600 + i * 250);
    });
    const bar = $(".mini-bar i");
    if (bar) M.animate(bar, { width: ["0%", "82%"] }, { duration: 1.4, delay: 1.1, ease });
  }

  // ---------- page: auth
  if (page === "auth" && canAnimate) {
    const img = $("[data-kenburns]");
    if (img) M.animate(img, { scale: [1.12, 1] }, { duration: 8, ease: "easeOut" });
    const sw = $("[data-switch]");
    if (sw) {
      const pill = $(".pill-bg", sw);
      const right = sw.dataset.switch === "right";
      pill.style.left = right ? "calc(50%)" : "4px";
      M.animate(pill, { x: right ? [-40, 0] : [40, 0] }, { type: "spring", stiffness: 300, damping: 26 });
      $$("form label, form .btn", sw.parentElement).length && M.animate($$(".auth-form form > *"), { opacity: [0, 1], y: [12, 0] }, { delay: M.stagger(0.05, { startDelay: 0.2 }), duration: 0.4 });
    }
  } else if (page === "auth") {
    const sw = $("[data-switch]");
    if (sw) $(".pill-bg", sw).style.left = sw.dataset.switch === "right" ? "calc(50%)" : "4px";
  }

  // ---------- page: idea wizard
  const wizard = $("[data-wizard]");
  if (wizard) {
    const steps = $$("[data-wstep]", wizard);
    const prev = $("[data-prev]", wizard), next = $("[data-next]", wizard), submit = $("[data-submit]", wizard);
    const label = $("[data-step-label]"), progress = $("[data-progress]");
    let at = 0;
    const show = (to, dir) => {
      const from = steps[at];
      at = to;
      steps.forEach((s, i) => s.classList.toggle("on", i === at));
      prev.hidden = at === 0;
      next.hidden = at === steps.length - 1;
      submit.hidden = at !== steps.length - 1;
      label.textContent = `Step ${at + 1} of ${steps.length}`;
      const pct = ((at + 1) / steps.length) * 100 + "%";
      if (canAnimate) {
        M.animate(progress, { width: pct }, { duration: 0.5, ease });
        M.animate(steps[at], { opacity: [0, 1], x: [dir * 40, 0] }, { duration: 0.45, ease });
        M.animate($$("label, .option, h2, p", steps[at]), { opacity: [0, 1], y: [10, 0] }, { delay: M.stagger(0.03), duration: 0.35 });
      } else progress.style.width = pct;
      const first = $("input:not([type=hidden]), textarea, select", steps[at]);
      if (first && dir) first.focus({ preventScroll: true });
      if (from && dir) window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    };
    const valid = () => {
      const fields = $$("input, textarea, select", steps[at]);
      for (const f of fields) if (!f.checkValidity()) { f.reportValidity(); return false; }
      return true;
    };
    next.addEventListener("click", () => { if (valid()) show(at + 1, 1); });
    prev.addEventListener("click", () => show(at - 1, -1));
    wizard.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target.tagName === "INPUT" && at < steps.length - 1) { e.preventDefault(); next.click(); }
    });
    show(0, 0);
  }

  // ---------- live progress while the AI works
  const progressBox = $("[data-poll]");
  if (progressBox) {
    const url = progressBox.dataset.poll;
    const waitFor = progressBox.dataset.until;
    const items = $$("[data-step]", progressBox);
    const orb = $("[data-orb]", progressBox);
    if (orb && canAnimate) M.animate(orb, { scale: [1, 1.06, 1], rotate: [0, 4, -4, 0] }, { duration: 2.4, repeat: Infinity, ease: "easeInOut" });
    const tick = async () => {
      try {
        const data = await (await fetch(url, { headers: { Accept: "application/json" } })).json();
        if (waitFor ? data.status !== waitFor : !["pending", "running"].includes(data.status)) {
          if (canAnimate) await M.animate(progressBox, { opacity: 0, scale: 0.98 }, { duration: 0.3 });
          location.reload();
          return;
        }
        const done = new Set((data.steps || []).map((s) => s.step));
        if (done.has("summarise")) done.add("research");
        let marked = false;
        items.forEach((li) => {
          const isDone = done.has(li.dataset.step);
          if (isDone && !li.classList.contains("done") && canAnimate) M.animate(li, { scale: [1.04, 1] }, { type: "spring", stiffness: 400, damping: 15 });
          li.classList.toggle("done", isDone);
          const active = !marked && !isDone;
          li.classList.toggle("active", active);
          if (active) marked = true;
        });
      } catch (e) { /* keep polling */ }
      setTimeout(tick, 1000);
    };
    tick();
  }

  // funder program page: matching runs in the background right after publishing
  const reloader = $("[data-poll-reload]");
  if (reloader) {
    let tries = 0;
    try { tries = Number(sessionStorage.getItem("sb-reload-" + location.pathname) || 0); } catch (e) {}
    if (tries < 3) setTimeout(() => {
      try { sessionStorage.setItem("sb-reload-" + location.pathname, String(tries + 1)); } catch (e) {}
      location.reload();
    }, 3000);
  }

  // ---------- menus, confirms, avatar preview
  $$("[data-menu]").forEach((menu) => {
    const btn = $("button", menu), pop = $(".menu-pop", menu);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !menu.classList.contains("open");
      menu.classList.toggle("open", open);
      btn.setAttribute("aria-expanded", String(open));
      if (open && canAnimate) M.animate(pop, { opacity: [0, 1], y: [-6, 0], scale: [0.97, 1] }, { duration: 0.2 });
    });
    document.addEventListener("click", () => { menu.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu.classList.remove("open"); });
  });
  $$("[data-confirm]").forEach((btn) =>
    btn.addEventListener("click", (e) => { if (!confirm(btn.dataset.confirm)) e.preventDefault(); })
  );
  const avatarInput = $("[data-avatar-input]");
  if (avatarInput) avatarInput.addEventListener("change", () => {
    const file = avatarInput.files[0];
    if (!file) return;
    const img = $("[data-avatar-preview]");
    img.src = URL.createObjectURL(file);
    if (canAnimate) M.animate(img, { scale: [0.8, 1], rotate: [-6, 0] }, { type: "spring", stiffness: 260, damping: 14 });
  });

  // safety net: never leave content invisible if Motion or inView didn't run
  if (canAnimate) setTimeout(() => $$("[data-reveal], [data-stagger]").forEach((el) => {
    if (!el.dataset.revealed && el.getBoundingClientRect().top < innerHeight) reveal(el);
  }), 1500);
})();
