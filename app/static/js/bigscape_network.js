(function () {
  const viewer = document.getElementById("bigscape-network-viewer");
  if (!viewer) return;

  const gcfInput = document.getElementById("bigscape-gcf-input");
  const networkSelect = document.getElementById("bigscape-network-select");
  const nodeSearch = document.getElementById("bigscape-node-search");
  const statusEl = document.getElementById("bigscape-viewer-status");
  const graphEl = document.getElementById("bigscape-cytoscape");
  const detailsEl = document.getElementById("bigscape-node-details");
  const openBGCLink = document.getElementById("bigscape-open-bgc");
  const downloadJsonLink = document.getElementById("bigscape-download-json");
  const gcfPattern = /^BGS-GCF-C03-\d{4}$/;
  let cy = null;
  let currentPayload = null;
  let networks = [];

  function setStatus(message, mode) {
    statusEl.textContent = message;
    statusEl.dataset.mode = mode || "info";
  }

  function safeGcf(value) {
    const candidate = String(value || "").trim().toUpperCase();
    return gcfPattern.test(candidate) ? candidate : "";
  }

  async function fetchJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const text = await response.text();
    let payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (error) {
      console.error("Failed to parse BiG-SCAPE response", error);
      throw new Error("The network service returned an unreadable response.");
    }
    if (!response.ok) {
      const detail = payload.detail || payload.message || {};
      const message = typeof detail === "string" ? detail : detail.message;
      throw new Error(message || "The selected network could not be loaded.");
    }
    return payload;
  }

  function populateNetworks(items) {
    networks = items || [];
    networkSelect.innerHTML = "";
    networks.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.network_id;
      option.textContent = `${item.cutoff} · ${item.class} · ${item.mapped_node_count} nodes · ${item.mapped_edge_count} edges${item.renderable ? "" : " · download only"}`;
      option.disabled = !item.renderable;
      networkSelect.appendChild(option);
    });
  }

  function render(payload) {
    currentPayload = payload;
    const nodes = payload.elements.nodes || [];
    const edges = payload.elements.edges || [];
    if (cy) {
      cy.destroy();
      cy = null;
    }
    graphEl.classList.remove("empty-viewer");
    if (!nodes.length) {
      graphEl.textContent = "No mapped BGS nodes are available for this selection.";
      graphEl.classList.add("empty-viewer");
      setStatus("No mapped BGS nodes are available for this selection.", "empty");
      resetDetails();
      return;
    }
    graphEl.textContent = "";
    cy = cytoscape({
      container: graphEl,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "mapData(protein_count, 0, 40, #cbb7df, #57068c)",
            "border-color": "#ffffff",
            "border-width": 2,
            color: "#202124",
            label: "",
            "font-size": 7,
            "text-valign": "top",
            "text-halign": "center",
            "text-margin-y": -5,
            width: 20,
            height: 20,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.3,
            "line-color": "#b7a3c7",
            opacity: 0.55,
            "curve-style": "haystack",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#2b004f",
            "border-width": 5,
            "background-color": "#7b3fa1",
            label: "data(label)",
          },
        },
        {
          selector: ".faded",
          style: { opacity: 0.2 },
        },
        {
          selector: ".highlighted",
          style: { opacity: 1, "border-color": "#2b004f", "border-width": 4, label: "data(label)" },
        },
      ],
      layout: layoutFor(nodes.length, edges.length),
    });
    cy.on("tap", "node", (event) => selectNode(event.target));
    cy.on("tap", (event) => {
      if (event.target === cy) clearSelection();
    });
    const label = payload.metadata.gcf_accession || payload.metadata.network_id || "selection";
    if (downloadJsonLink) {
      if (payload.metadata.gcf_accession) {
        downloadJsonLink.href = `/api/bigscape/gcfs/${encodeURIComponent(payload.metadata.gcf_accession)}/network`;
      } else if (payload.metadata.network_id) {
        downloadJsonLink.href = `/api/bigscape/networks/${encodeURIComponent(payload.metadata.network_id)}`;
      }
      downloadJsonLink.hidden = false;
    }
    setStatus(`${label}: ${nodes.length.toLocaleString()} nodes and ${edges.length.toLocaleString()} edges loaded.`, "ready");
    resetDetails();
  }

  function layoutFor(nodeCount, edgeCount) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return { name: "grid", fit: true, padding: 32 };
    }
    if (nodeCount <= 1 || edgeCount === 0) {
      return { name: "grid", fit: true, padding: 32 };
    }
    if (nodeCount < 20) {
      return { name: "concentric", fit: true, padding: 36, animate: false };
    }
    return { name: "cose", fit: true, padding: 36, animate: false, randomize: false };
  }

  function selectNode(node) {
    if (!cy) return;
    cy.elements().removeClass("highlighted faded");
    const neighborhood = node.closedNeighborhood();
    cy.elements().difference(neighborhood).addClass("faded");
    neighborhood.addClass("highlighted");
    node.select();
    const data = node.data();
    detailsEl.innerHTML = "";
    [
      ["BGC accession", data.bgc_accession],
      ["GCF accession", data.gcf_accession],
      ["MAG accession", data.mag_accession],
      ["BiG-SCAPE class", data.bigscape_class],
      ["Proteins", data.protein_count],
      ["Predicted structures", data.structure_count],
      ["Original identifier", data.original_bgc_id],
    ].forEach(([label, value]) => {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = value || "Not available";
      detailsEl.append(dt, dd);
    });
    openBGCLink.href = data.bgc_url || `/bgcs/${data.bgc_accession}`;
    openBGCLink.hidden = false;
    setStatus(`Selected ${data.bgc_accession}.`, "ready");
  }

  function resetDetails() {
    detailsEl.innerHTML = "<dt>Status</dt><dd>Select a node to inspect metadata.</dd>";
    openBGCLink.hidden = true;
  }

  function clearSelection() {
    if (!cy) return;
    cy.elements().removeClass("highlighted faded");
    cy.nodes().unselect();
    resetDetails();
  }

  async function loadGcf(value) {
    const gcf = safeGcf(value || gcfInput.value);
    if (!gcf) {
      setStatus("Enter a valid BGS-GCF-C03 accession.", "error");
      return;
    }
    gcfInput.value = gcf;
    setStatus(`Loading ${gcf}...`, "loading");
    try {
      render(await fetchJson(`/api/bigscape/gcfs/${encodeURIComponent(gcf)}/network`));
    } catch (error) {
      console.error("BiG-SCAPE GCF load failed", error);
      setStatus(error.message || "This GCF network could not be loaded.", "error");
    }
  }

  async function loadNetwork() {
    const id = networkSelect.value;
    if (!id) {
      setStatus("Select a renderable network file.", "error");
      return;
    }
    setStatus("Loading selected network...", "loading");
    try {
      render(await fetchJson(`/api/bigscape/networks/${encodeURIComponent(id)}`));
    } catch (error) {
      console.error("BiG-SCAPE network load failed", error);
      setStatus(error.message || "This network is available for download but exceeds the interactive viewer size limit.", "error");
    }
  }

  function searchNode() {
    if (!cy) return;
    const term = String(nodeSearch.value || "").trim().toLowerCase();
    if (!term) {
      clearSelection();
      return;
    }
    const match = cy.nodes().filter((node) => {
      const data = node.data();
      return [data.bgc_accession, data.original_bgc_id, data.mag_accession]
        .some((value) => String(value || "").toLowerCase().includes(term));
    }).first();
    if (match.length > 0) {
      cy.center(match);
      selectNode(match);
    } else {
      setStatus("No node matched that search term.", "empty");
    }
  }

  function resetLayout() {
    if (!cy || !currentPayload) return;
    const nodes = currentPayload.elements.nodes || [];
    const edges = currentPayload.elements.edges || [];
    cy.layout(layoutFor(nodes.length, edges.length)).run();
  }

  viewer.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    if (action === "load-gcf") loadGcf();
    if (action === "load-network") loadNetwork();
    if (action === "fit" && cy) cy.fit(undefined, 32);
    if (action === "reset") resetLayout();
    if (action === "zoom-in" && cy) cy.zoom({ level: cy.zoom() * 1.2, renderedPosition: { x: graphEl.clientWidth / 2, y: graphEl.clientHeight / 2 } });
    if (action === "zoom-out" && cy) cy.zoom({ level: cy.zoom() / 1.2, renderedPosition: { x: graphEl.clientWidth / 2, y: graphEl.clientHeight / 2 } });
    if (action === "fullscreen") graphEl.requestFullscreen && graphEl.requestFullscreen();
    if (action === "clear") clearSelection();
  });
  nodeSearch.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchNode();
    }
  });
  gcfInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadGcf();
    }
  });

  async function init() {
    if (typeof cytoscape !== "function") {
      setStatus("The network viewer library did not load.", "error");
      return;
    }
    try {
      const metadata = await fetchJson("/api/bigscape/networks");
      populateNetworks(metadata.items);
      const requested = safeGcf(viewer.dataset.selectedGcf);
      const fallback = safeGcf(viewer.dataset.defaultGcf);
      await loadGcf(requested || fallback);
    } catch (error) {
      console.error("BiG-SCAPE viewer initialization failed", error);
      setStatus(error.message || "Network metadata could not be loaded.", "error");
    }
  }

  init();
})();
