(function () {
  const ERROR_MESSAGES = {
    "missing-url": "Missing validated structure URL",
    "viewer-library-missing": "3Dmol library is unavailable",
    "http-error": "CIF request failed",
    "cors-error": "CIF request was blocked",
    "empty-response": "CIF response was empty",
    "html-response": "CIF endpoint returned HTML instead of structure data",
    "cif-parse-error": "CIF parser could not read the structure",
    "empty-model": "CIF parser returned no atoms",
    "render-error": "Structure renderer failed",
  };

  function setFailure(container, category, error) {
    const message = ERROR_MESSAGES[category] || "Structure loading failed";
    container.classList.remove("structure-ready");
    container.classList.add("structure-error-state");
    container.dataset.viewerStatus = "error";
    container.dataset.viewerError = category;
    container.innerHTML = [
      '<div class="structure-error">',
      "<div>",
      "<strong>Structure could not be loaded.</strong>",
      "<span>Download the CIF file instead.</span>",
      "</div>",
      "</div>",
    ].join("");
    console.error("[structure-viewer]", category, message, error);
  }

  function atomCountFor(model, viewer) {
    if (model && typeof model.selectedAtoms === "function") {
      return model.selectedAtoms({}).length;
    }
    if (viewer && Array.isArray(viewer.models) && viewer.models[0] && typeof viewer.models[0].selectedAtoms === "function") {
      return viewer.models[0].selectedAtoms({}).length;
    }
    return 0;
  }

  function fitMolecule(viewer, zoom = 1.22) {
    if (!viewer) return;
    if (typeof viewer.resize === "function") viewer.resize();
    viewer.zoomTo();
    if (typeof viewer.zoom === "function") viewer.zoom(zoom);
    viewer.center();
    viewer.render();
  }

  function setCartoon(viewer) {
    viewer.removeAllSurfaces();
    viewer.setStyle({}, { cartoon: { color: "spectrum" } });
    fitMolecule(viewer);
  }

  function setPlddt(viewer) {
    viewer.removeAllSurfaces();
    viewer.setStyle({}, { cartoon: { colorscheme: { prop: "b", gradient: "roygb", min: 50, max: 100 } } });
    fitMolecule(viewer);
  }

  function setSurface(viewer) {
    viewer.setStyle({}, { cartoon: { color: "spectrum", opacity: 0.55 } });
    viewer.removeAllSurfaces();
    if (window.$3Dmol && window.$3Dmol.SurfaceType) {
      viewer.addSurface(window.$3Dmol.SurfaceType.VDW, { opacity: 0.28, color: "white" }, {});
    }
    fitMolecule(viewer, 1.12);
  }

  async function loadStructureViewer(container, url = container?.dataset?.cif) {
    if (!container) return null;
    container.dataset.viewerStatus = "loading";
    container.dataset.viewerError = "";

    if (!url) {
      const error = new Error("Missing validated structure URL");
      setFailure(container, "missing-url", error);
      return null;
    }

    if (!window.$3Dmol || typeof window.$3Dmol.createViewer !== "function") {
      const error = new Error("3Dmol library is unavailable");
      setFailure(container, "viewer-library-missing", error);
      return null;
    }

    let cifText = "";
    try {
      const response = await fetch(url, {
        method: "GET",
        mode: "cors",
        credentials: "omit",
        cache: "no-store",
      });
      if (!response.ok) {
        const error = new Error(`CIF request failed with HTTP ${response.status}`);
        error.status = response.status;
        setFailure(container, "http-error", error);
        return null;
      }
      cifText = await response.text();
    } catch (error) {
      setFailure(container, "cors-error", error);
      return null;
    }

    if (!cifText.trim()) {
      setFailure(container, "empty-response", new Error("CIF response was empty"));
      return null;
    }
    if (/^\s*</.test(cifText)) {
      setFailure(container, "html-response", new Error("CIF endpoint returned HTML instead of structure data"));
      return null;
    }

    let viewer = null;
    let model = null;
    try {
      container.innerHTML = "";
      viewer = window.$3Dmol.createViewer(container, { backgroundColor: "#f6f8fa" });
      window.__phrcStructureViewer = viewer;
      model = viewer.addModel(cifText, "cif");
    } catch (error) {
      setFailure(container, "cif-parse-error", error);
      return null;
    }

    const atomCount = atomCountFor(model, viewer);
    if (atomCount <= 0) {
      setFailure(container, "empty-model", new Error("CIF parser returned no atoms"));
      return null;
    }

    try {
      setPlddt(viewer);
      container.classList.remove("structure-error-state");
      container.classList.add("structure-ready");
      container.dataset.viewerStatus = "loaded";
      container.dataset.viewerError = "";
      container.dataset.atomCount = String(atomCount);
      container.insertAdjacentHTML("beforeend", '<div class="structure-status sr-only">Interactive structure loaded</div>');
      setTimeout(() => fitMolecule(viewer, 1.28), 120);
    } catch (error) {
      setFailure(container, "render-error", error);
      return null;
    }

    return { viewer, model, atomCount };
  }

  function bindControls(container, state) {
    const controls = document.querySelector(".viewer-controls");
    if (!controls || !state?.viewer || !state?.model) return;
    let spinning = false;
    let resizeFrame = null;

    controls.addEventListener("click", (event) => {
      const button = event.target.closest("[data-viewer-action]");
      if (!button) return;
      const action = button.getAttribute("data-viewer-action");
      if (action === "reset") fitMolecule(state.viewer, 1.28);
      if (action === "spin") {
        spinning = !spinning;
        state.viewer.spin(spinning);
        button.classList.toggle("active", spinning);
      }
      if (action === "cartoon") setCartoon(state.viewer);
      if (action === "surface") setSurface(state.viewer);
      if (action === "plddt") setPlddt(state.viewer);
      if (action === "fullscreen" && container.requestFullscreen) container.requestFullscreen();
    });

    window.addEventListener("resize", () => {
      if (resizeFrame) cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => fitMolecule(state.viewer, 1.18));
    });
  }

  window.StaticStructureViewer = {
    loadStructureViewer,
    bindControls,
  };

  document.addEventListener("DOMContentLoaded", async () => {
    const container = document.getElementById("viewer");
    if (!container) return;
    const state = await loadStructureViewer(container);
    bindControls(container, state);
  });
})();
