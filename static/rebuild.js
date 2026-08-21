// Shared by reports.html (Monthly P&L) and reports_yearly.html (Yearly
// P&L) — both have an identical #rebuildForm/#rebuildProgress pair. See
// jobs.py / static/progress.js for the underlying job-polling mechanism.
document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('rebuildForm');
  if (!form) return;

  function resetButton(btn) {
    if (!btn) return;
    btn.disabled = false;
    btn.classList.remove('is-saving');
    if (btn.dataset.originalLabel) btn.textContent = btn.dataset.originalLabel;
  }

  form.addEventListener('submit', async function (e) {
    // Waits for ui.js's existing data-confirm handler to run first — it
    // shows the "are you sure" dialog and only re-submits (with
    // dataset.confirmed = "1") once the person actually confirms.
    if (this.hasAttribute('data-confirm') && this.dataset.confirmed !== '1') return;
    e.preventDefault();
    const btn = document.getElementById('rebuildBtn');
    const panel = document.getElementById('rebuildProgress');
    panel.style.display = 'block';
    try {
      const res = await fetch(this.action, {
        method: 'POST',
        headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
      });
      const data = await res.json();
      if (!res.ok || !data.job_id) throw new Error('Could not start the rebuild.');
      window.VZProgress.poll(data.job_id, '/jobs/status', {}, {
        onUpdate: (d) => window.VZProgress.render(panel, d),
        onDone: (d) => {
          resetButton(btn);
          window.VZToast.show(d.message || (d.ok ? 'Rebuild complete.' : 'Rebuild failed.'), d.ok ? 'success' : 'error');
          setTimeout(() => window.location.reload(), 900);
        },
        onError: (d) => {
          resetButton(btn);
          window.VZProgress.render(panel, { status: 'error', steps: ['Rebuild'], current: 0, message: d.message });
          window.VZToast.show(d.message || 'Rebuild failed.', 'error');
        },
      });
    } catch (err) {
      resetButton(btn);
      panel.style.display = 'none';
      window.VZToast.show('Could not start the rebuild.', 'error');
    }
  });
});
