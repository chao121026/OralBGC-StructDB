document.addEventListener('DOMContentLoaded', async () => {
  const el = document.getElementById('viewer');
  if (!el) return;

  const showError = () => {
    el.classList.remove('structure-ready');
    el.innerHTML = '<div class="structure-error">Structure could not be loaded.</div>';
  };

  if (!window.$3Dmol || !el.dataset.cif) {
    showError();
    return;
  }

  try {
    const res = await fetch(el.dataset.cif);
    if (!res.ok) throw new Error('CIF unavailable');
    const cif = await res.text();

    el.innerHTML = '';
    const viewer = $3Dmol.createViewer(el, { backgroundColor: 'white' });
    window.__phrcStructureViewer = viewer;
    viewer.addModel(cif, 'cif');
    viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
    viewer.zoomTo();
    viewer.render();
    if (typeof viewer.resize === 'function') viewer.resize();
    el.classList.add('structure-ready');

    let resizeFrame = null;
    window.addEventListener('resize', () => {
      if (resizeFrame) cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        if (typeof viewer.resize === 'function') viewer.resize();
        viewer.render();
      });
    });
  } catch (error) {
    showError();
  }
});
