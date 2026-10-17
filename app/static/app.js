// Live progress while the models work, plus small form helpers. No framework needed.
(function () {
  const progress = document.querySelector("[data-poll]");
  if (progress) {
    const url = progress.dataset.poll;
    const waitFor = progress.dataset.until; // application pages: reload once status leaves this value
    const items = [...progress.querySelectorAll("[data-step]")];
    const tick = async () => {
      try {
        const res = await fetch(url, { headers: { Accept: "application/json" } });
        const data = await res.json();
        if (waitFor ? data.status !== waitFor : !["pending", "running"].includes(data.status)) {
          location.reload();
          return;
        }
        const done = new Set((data.steps || []).map((s) => s.step));
        let marked = false;
        items.forEach((li) => {
          li.classList.toggle("done", done.has(li.dataset.step));
          const isNext = !marked && !done.has(li.dataset.step);
          li.classList.toggle("active", isNext);
          if (isNext) marked = true;
        });
      } catch (e) { /* keep polling */ }
      setTimeout(tick, 1200);
    };
    tick();
  }

  // Sponsor program page: matching runs in the background right after publishing.
  const reloader = document.querySelector("[data-poll-reload]");
  if (reloader) {
    let tries = 0;
    try { tries = Number(sessionStorage.getItem("sb-reload-" + location.pathname) || 0); } catch (e) {}
    if (tries < 3) {
      setTimeout(() => {
        try { sessionStorage.setItem("sb-reload-" + location.pathname, String(tries + 1)); } catch (e) {}
        location.reload();
      }, 3000);
    }
  }

  document.querySelectorAll("[data-confirm]").forEach((btn) =>
    btn.addEventListener("click", (e) => { if (!confirm(btn.dataset.confirm)) e.preventDefault(); })
  );
})();
