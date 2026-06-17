(function () {
  "use strict";

  function setState(container, className, message) {
    container.classList.remove("structure-loading", "structure-ready", "structure-error");
    container.classList.add(className);
    container.innerHTML = `<div class="${className}">${message}</div>`;
  }

  function bindControls(panel, viewer, styles) {
    const buttons = panel.querySelectorAll("[data-static-viewer-action]");
    let spinning = false;
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.getAttribute("data-static-viewer-action");
        if (action === "reset") {
          viewer.zoomTo();
          viewer.render();
        } else if (action === "spin") {
          spinning = !spinning;
          viewer.spin(spinning);
          button.classList.toggle("active", spinning);
        } else if (action === "cartoon") {
          viewer.setStyle({}, styles.cartoon);
          viewer.render();
        } else if (action === "surface") {
          viewer.setStyle({}, styles.surface);
          viewer.render();
        }
      });
    });
  }

  async function load(container, cifUrl, accession) {
    if (!container || !cifUrl) return;
    if (!window.$3Dmol?.createViewer) {
      setState(container, "structure-error", "The local structure viewer library is unavailable. Use the CIF download link.");
      return;
    }
    try {
      setState(container, "structure-loading", "Loading predicted structure...");
      const response = await fetch(cifUrl, { mode: "cors", credentials: "omit" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const cifText = await response.text();
      container.innerHTML = "";
      const viewer = window.$3Dmol.createViewer(container, { backgroundColor: "white" });
      viewer.addModel(cifText, "cif");
      const styles = {
        cartoon: { cartoon: { color: "spectrum" } },
        surface: { cartoon: { color: "spectrum" }, surface: { opacity: 0.45, color: "white" } },
      };
      viewer.setStyle({}, styles.cartoon);
      viewer.zoomTo();
      viewer.render();
      container.classList.remove("structure-loading", "structure-error");
      container.classList.add("structure-ready");
      container.setAttribute("aria-label", `Predicted structure viewer for ${accession || "selected structure"}`);
      bindControls(container.closest("[data-static-structure-panel]") || document, viewer, styles);
    } catch {
      setState(container, "structure-error", "Browser CIF loading failed. Use the verified CIF download link.");
    }
  }

  window.StaticStructureViewer = { load };
}());
