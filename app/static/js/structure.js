document.addEventListener('DOMContentLoaded', async () => {
  const el = document.getElementById('viewer');
  if (!el) return;

  const controls = document.querySelector('.viewer-controls');
  let viewer = null;
  let model = null;
  let spinning = false;

  const showError = () => {
    el.classList.remove('structure-ready');
    el.innerHTML = '<div class="structure-error">Structure could not be loaded.</div>';
  };

  const fitMolecule = (zoom = 1.22) => {
    if (!viewer) return;
    if (typeof viewer.resize === 'function') viewer.resize();
    viewer.zoomTo();
    if (typeof viewer.zoom === 'function') viewer.zoom(zoom);
    viewer.center();
    viewer.render();
  };

  const setCartoon = () => {
    viewer.removeAllSurfaces();
    viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
    fitMolecule();
  };

  const setPlddt = () => {
    viewer.removeAllSurfaces();
    viewer.setStyle({}, { cartoon: { colorscheme: { prop: 'b', gradient: 'roygb', min: 50, max: 100 } } });
    fitMolecule();
  };

  const setSurface = () => {
    viewer.setStyle({}, { cartoon: { color: 'spectrum', opacity: 0.55 } });
    viewer.removeAllSurfaces();
    if (window.$3Dmol && $3Dmol.SurfaceType) {
      viewer.addSurface($3Dmol.SurfaceType.VDW, { opacity: 0.28, color: 'white' }, {});
    }
    fitMolecule(1.12);
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
    viewer = $3Dmol.createViewer(el, { backgroundColor: '#f6f8fa' });
    window.__phrcStructureViewer = viewer;
    model = viewer.addModel(cif, 'cif');
    setPlddt();
    el.classList.add('structure-ready');
    setTimeout(() => fitMolecule(1.28), 120);

    controls?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-viewer-action]');
      if (!button || !viewer || !model) return;
      const action = button.getAttribute('data-viewer-action');
      if (action === 'reset') fitMolecule(1.28);
      if (action === 'spin') {
        spinning = !spinning;
        viewer.spin(spinning);
        button.classList.toggle('active', spinning);
      }
      if (action === 'cartoon') setCartoon();
      if (action === 'surface') setSurface();
      if (action === 'plddt') setPlddt();
      if (action === 'fullscreen' && el.requestFullscreen) el.requestFullscreen();
    });

    let resizeFrame = null;
    window.addEventListener('resize', () => {
      if (resizeFrame) cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => fitMolecule(1.18));
    });
  } catch (error) {
    showError();
  }
});
