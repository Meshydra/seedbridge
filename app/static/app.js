// SeedBridge front end: restrained Motion (motion.dev) entrances, live progress, form helpers.
// Motion rules: 200-500ms, ease-out on entry, transform/opacity only, nothing loops.
(function () {
  const M = window.Motion;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canAnimate = !!M && !reduce;
  const page = document.body.dataset.page;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const ease = [0.16, 1, 0.3, 1];

  if (canAnimate) document.documentElement.classList.add("motion-ready");

  // ---------- numbers, rings, bars fill in once when they come into view
  function countUp(el, delay = 0) {
    const to = Number(el.dataset.count);
    if (!canAnimate || !Number.isFinite(to) || to === 0) return;
    M.animate(0, to, { duration: 0.8, delay, ease, onUpdate: (v) => (el.textContent = Math.round(v)) });
  }
  function drawRing(wrap, delay = 0) {
    const arc = $("[data-ring-arc]", wrap);
    if (!arc || !canAnimate) return;
    M.animate(arc, { strokeDashoffset: [100, 100 - Number(wrap.dataset.ring || 0)] }, { duration: 0.9, delay, ease });
    $$("[data-count]", wrap).forEach((n) => countUp(n, delay));
  }
  function growBars(scope, delay = 0) {
    if (!canAnimate) return;
    $$("[data-bar]", scope).forEach((bar, i) =>
      M.animate(bar, { width: ["0%", bar.style.width] }, { duration: 0.6, delay: delay + i * 0.04, ease }));
  }

  function reveal(el) {
    if (el.dataset.revealed) return;
    el.dataset.revealed = "1";
    if (el.hasAttribute("data-stagger")) {
      M.animate([...el.children], { opacity: [0, 1], y: [12, 0] }, { duration: 0.45, delay: M.stagger(0.05), ease });
      $$("[data-ring]", el).forEach((r) => drawRing(r, 0.15));
    } else {
      M.animate(el, { opacity: [0, 1], y: [16, 0] }, { duration: 0.5, ease });
      $$("[data-ring]", el).forEach((r) => drawRing(r, 0.1));
      growBars(el, 0.2);
      $$("[data-count]", el).forEach((n) => { if (!n.closest("[data-ring]")) countUp(n, 0.1); });
    }
  }
  if (canAnimate) {
    $$("[data-reveal], [data-stagger]").forEach((el) => M.inView(el, () => reveal(el), { amount: 0.2 }));
    $$("[data-pop]").forEach((el) => M.animate(el, { opacity: [0, 1], y: [12, 0] }, { duration: 0.45, ease }));
    $$("[data-flash]").forEach((el) => M.animate(el, { opacity: [0, 1], y: [-6, 0] }, { duration: 0.3, ease }));
    // safety net: never leave content hidden if an observer didn't fire
    setTimeout(() => $$("[data-reveal], [data-stagger]").forEach((el) => {
      if (!el.dataset.revealed && el.getBoundingClientRect().top < innerHeight) reveal(el);
    }), 1200);
  }

  // ---------- home: one composed entrance
  if (page === "home" && canAnimate) {
    M.animate($$("[data-hero]"), { opacity: [0, 1], y: [16, 0] }, { duration: 0.6, delay: M.stagger(0.08), ease });
    const art = $("[data-hero-art]");
    if (art) M.animate(art, { opacity: [0, 1], scale: [0.98, 1] }, { duration: 0.7, delay: 0.15, ease });
    M.animate($$("[data-float]"), { opacity: [0, 1], y: [10, 0] }, { duration: 0.5, delay: M.stagger(0.12, { startDelay: 0.6 }), ease });
    const meter = $(".meter i");
    if (meter) M.animate(meter, { width: ["0%", "82%"] }, { duration: 0.9, delay: 0.8, ease });
  }

  // ---------- auth: segmented control
  const seg = $("[data-switch]");
  if (seg) {
    const pill = $(".pill-bg", seg);
    const right = seg.dataset.switch === "right";
    pill.style.left = right ? "50%" : "3px";
    if (canAnimate) M.animate(pill, { x: [right ? -16 : 16, 0] }, { duration: 0.25, ease });
  }

  // ---------- idea wizard
  const wizard = $("[data-wizard]");
  if (wizard) {
    const steps = $$("[data-wstep]", wizard);
    const prev = $("[data-prev]", wizard), next = $("[data-next]", wizard), submit = $("[data-submit]", wizard);
    const label = $("[data-step-label]"), dots = $$("[data-dots] i");
    let at = 0;
    const show = (to, dir) => {
      at = to;
      steps.forEach((s, i) => s.classList.toggle("on", i === at));
      dots.forEach((d, i) => d.classList.toggle("on", i <= at));
      prev.hidden = at === 0;
      next.hidden = at === steps.length - 1;
      submit.hidden = at !== steps.length - 1;
      label.textContent = `Step ${at + 1} of ${steps.length}`;
      if (canAnimate && dir) M.animate(steps[at], { opacity: [0, 1], x: [dir * 16, 0] }, { duration: 0.25, ease });
      const first = $("input:not([type=hidden]):not([type=radio]), textarea, select", steps[at]);
      if (first && dir) first.focus({ preventScroll: true });
      if (dir) window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    };
    const valid = () => {
      for (const f of $$("input, textarea, select", steps[at])) if (!f.checkValidity()) { f.reportValidity(); return false; }
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
  const box = $("[data-poll]");
  if (box) {
    const url = box.dataset.poll, waitFor = box.dataset.until, items = $$("[data-step]", box);
    const tick = async () => {
      try {
        const data = await (await fetch(url, { headers: { Accept: "application/json" } })).json();
        if (waitFor ? data.status !== waitFor : !["pending", "running"].includes(data.status)) { location.reload(); return; }
        const done = new Set((data.steps || []).map((s) => s.step));
        if (done.has("summarise")) done.add("research");
        let marked = false;
        items.forEach((li) => {
          const isDone = done.has(li.dataset.step);
          li.classList.toggle("done", isDone);
          li.classList.toggle("active", !marked && !isDone);
          if (!marked && !isDone) marked = true;
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

  // ---------- account menu
  $$("[data-menu]").forEach((menu) => {
    const btn = $("button", menu), pop = $(".menu-pop", menu);
    const close = () => { menu.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); };
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !menu.classList.contains("open");
      menu.classList.toggle("open", open);
      btn.setAttribute("aria-expanded", String(open));
      if (open && canAnimate) M.animate(pop, { opacity: [0, 1], y: [-4, 0] }, { duration: 0.15, ease: "easeOut" });
    });
    document.addEventListener("click", close);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  });

  // ---------- small form helpers
  $$("[data-confirm]").forEach((btn) =>
    btn.addEventListener("click", (e) => { if (!confirm(btn.dataset.confirm)) e.preventDefault(); }));
  $$("[data-counted]").forEach((ta) => {
    const out = $(`[data-counter-for="${ta.dataset.counted}"]`);
    const max = ta.maxLength;
    ta.addEventListener("input", () => { out.textContent = `${ta.value.length} / ${max}`; });
  });
  const avatarInput = $("[data-avatar-input]");
  if (avatarInput) avatarInput.addEventListener("change", () => {
    const file = avatarInput.files[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    $$(".photo-row .avatar, [data-avatar-preview]").forEach((img) => (img.src = url));
  });
})();
