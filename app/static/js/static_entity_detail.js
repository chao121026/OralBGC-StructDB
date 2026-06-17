(function () {
  "use strict";

  const configEl = document.getElementById("static-entity-config");
  const root = document.getElementById("static-entity-root");
  if (!configEl || !root) return;

  const config = JSON.parse(configEl.textContent);
  const html = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));

  function relationLink(accession) {
    if (!accession) return "";
    if (accession.startsWith("BGS-MAG-")) return `<a href="${basePath()}/mag/?id=${encodeURIComponent(accession)}">${html(accession)}</a>`;
    if (accession.startsWith("BGS-BGC-")) return `<a href="${basePath()}/bgc/?id=${encodeURIComponent(accession)}">${html(accession)}</a>`;
    if (accession.startsWith("BGS-GCF-")) return `<a href="${basePath()}/gcf/?id=${encodeURIComponent(accession)}">${html(accession)}</a>`;
    if (accession.startsWith("BGS-PRT-")) return `<a href="${basePath()}/protein/?id=${encodeURIComponent(accession)}">${html(accession)}</a>`;
    if (accession.startsWith("BGS-STR-")) return `<a href="${basePath()}/structure/?id=${encodeURIComponent(accession)}">${html(accession)}</a>`;
    if (accession.startsWith("BGS-PEP-")) return `<a href="${basePath()}/peptide/?id=${encodeURIComponent(accession)}">${html(accession)}</a>`;
    return html(accession);
  }

  function basePath() {
    return (window.ORALBGC_CONFIG && window.ORALBGC_CONFIG.basePath) || "";
  }

  function renderMessage(title, message) {
    root.innerHTML = `<h2>${html(title)}</h2><p class="status-note">${html(message)}</p>`;
  }

  function renderRecord(record) {
    const title = record.id || "Record";
    const browseHref = `${basePath()}/${config.entity}`;
    const entityLabel = (config.singular || config.entity || "record").toUpperCase();
    const relationRows = [
      ["MAG", record.mag],
      ["BGC", record.bgc],
      ["GCF", record.gcf],
      ["Protein", record.protein],
      ["Structure", record.structure],
    ].filter(([, value]) => value);
    const fieldRows = Object.entries(record)
      .filter(([key, value]) => !["url", "mag", "bgc", "gcf", "protein", "structure"].includes(key) && value !== null && value !== "")
      .map(([key, value]) => `<tr><th scope="row">${html(key.replaceAll("_", " "))}</th><td>${html(value)}</td></tr>`)
      .join("");
    root.innerHTML = `
      <section class="record-hero">
        <div class="page-shell">
          <p class="breadcrumb-line"><a href="${html(browseHref)}">${html(config.entity)}</a> / <span class="mono">${html(title)}</span></p>
          <h1 class="mono">${html(title)}</h1>
          <div class="record-meta"><span class="badge-token">PHRC</span><span class="badge-token">${html(entityLabel)}</span>${record.release_version ? `<span>Release ${html(record.release_version)}</span>` : ""}</div>
        </div>
      </section>
      <section class="page-shell section detail-grid">
        <div class="viewer-panel">
          <h2 class="mono">${html(title)}</h2>
          <h2>${config.viewerEnabled ? "3D Structure" : "Record context"}</h2>
          ${config.downloadOnly && !config.viewerEnabled ? '<p class="status-note">Download-only structure delivery. 3D visualization will be available after immutable release promotion.</p>' : ""}
          ${config.viewerEnabled ? `<div data-static-structure-panel><div data-static-structure-content><p class="status-note">Loading verified CIF resource metadata...</p></div></div>` : `<div class="metric-grid">${relationRows.map(([label, value]) => `<article><span>${html(label)}</span><strong>${relationLink(value)}</strong></article>`).join("")}</div>`}
        </div>
        <aside class="metric-panel">
          <h2>Download resources</h2>
          <div data-resource-content><p class="status-note">Resource metadata loads from bounded static JSON shards.</p></div>
        </aside>
      </section>
      <section class="page-shell section two-col">
        <div>
          <h2>Related records</h2>
          <details class="provenance-details" data-relationship-panel>
            <summary>Load related records</summary>
            <div data-relationship-content><p class="status-note">Relationship pages load on demand from static JSON shards.</p></div>
          </details>
        </div>
        <div>
          <h2>Public metadata</h2>
          <div class="table-wrap"><table class="data-table mobile-cards"><tbody>${fieldRows}</tbody></table></div>
        </div>
      </section>`;
    root.querySelector("[data-relationship-panel]")?.addEventListener("toggle", loadRelationships, { once: true });
    loadResources(record);
  }

  function entityKeyForId(id) {
    if (id.startsWith("BGS-MAG-")) return "mags";
    if (id.startsWith("BGS-BGC-")) return "bgcs";
    if (id.startsWith("BGS-GCF-")) return "gcfs";
    if (id.startsWith("BGS-PRT-")) return "proteins";
    if (id.startsWith("BGS-STR-")) return "structures";
    if (id.startsWith("BGS-PEP-")) return "peptides";
    return null;
  }

  function rangeFile(entity, id, manifest) {
    const prefix = manifest.prefix;
    const width = manifest.number_width || 6;
    const span = manifest.detail_range_span || 500;
    const number = Number(id.slice(prefix.length));
    if (!Number.isInteger(number) || number < 1) return null;
    const start = Math.floor((number - 1) / span) * span + 1;
    const end = start + span - 1;
    const pad = (value) => String(value).padStart(width, "0");
    return `range-${pad(start)}-${pad(end)}.json`;
  }

  async function loadRelationships(event) {
    if (!event.target.open) return;
    const content = event.target.querySelector("[data-relationship-content]");
    const id = (new URLSearchParams(location.search).get("id") || "").trim();
    const entity = entityKeyForId(id);
    const typeByEntity = {
      mags: "mag_to_bgc",
      bgcs: "bgc_to_protein",
      gcfs: "gcf_to_bgc",
      proteins: "protein_to_structure",
    };
    const type = typeByEntity[entity];
    if (!type) {
      content.innerHTML = '<p class="status-note">No related-record panel is available for this entity in the current release.</p>';
      return;
    }
    try {
      const manifest = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/relationships/manifest.json`).then((response) => response.json());
      const rel = manifest.relationships[type];
      const routing = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/relationships/${rel.routing_manifest}`).then((response) => response.json());
      const route = (routing.ranges || []).find((item) => id >= item.first_parent_accession && id <= item.last_parent_accession);
      const page = route?.pages?.[0];
      if (!page) {
        content.innerHTML = '<p class="status-note">No related records are present.</p>';
        return;
      }
      const payload = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/relationships/${page.file}`).then((response) => response.json());
      const rows = Array.isArray(payload) ? payload : (payload.rows || []);
      const related = rows.filter((row) => row.parent === id).slice(0, rel.page_size || 100);
      content.innerHTML = related.length
        ? `<ul class="related-list">${related.map((row) => `<li><a class="mono" href="${html(row.child_url)}">${html(row.child)}</a></li>`).join("")}</ul>`
        : '<p class="status-note">No related records are present.</p>';
    } catch {
      content.innerHTML = '<p class="status-note">Relationship data could not be loaded.</p>';
    }
  }

  function resourceRangeFile(entity, id, manifest) {
    const entityManifest = manifest.entities?.[entity];
    if (!entityManifest) return null;
    return entityManifest;
  }

  async function loadResources(record) {
    const content = root.querySelector("[data-resource-content]");
    if (!content || !config.resourceManifestUrl) return;
    const id = record.id || "";
    try {
      const manifest = await fetch(config.resourceManifestUrl).then((response) => response.json());
      const resources = [];
      const entityManifestRef = resourceRangeFile(config.entity, id, manifest);
      if (entityManifestRef) {
        const entityManifest = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/resources/${entityManifestRef.manifest}`).then((response) => response.json());
        const range = (entityManifest.ranges || []).find((item) => id >= item.first_accession && id <= item.last_accession);
        if (range) {
          const rows = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/resources/${config.entity}/${range.file}`).then((response) => response.json());
          resources.push(...rows.filter((row) => row.entity_accession === id));
        }
      }
      if (["bgcs", "proteins", "structures"].includes(config.entity) && manifest.bulk) {
        const bulk = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/resources/${manifest.bulk}`).then((response) => response.json());
        const wanted = {
          bgcs: ["bgc_gbk_archive", "bgc_bulk_archive"],
          proteins: ["protein_fasta", "protein_archive"],
          structures: ["structure_archive"],
        }[config.entity] || [];
        resources.push(...bulk.filter((row) => wanted.includes(row.resource_type)));
      }
      content.innerHTML = renderResources(resources);
      renderStructureViewer(resources, id);
    } catch {
      content.innerHTML = '<p class="status-note">Resource metadata could not be loaded.</p>';
      renderStructureViewer([], id);
    }
  }

  function downloadLabel(row) {
    const type = row.resource_type || "";
    if (type === "structure_cif") return "Download CIF";
    if (type === "mag_fasta") return "Download MAG FASTA";
    if (type === "protein_fasta") return "Download complete protein FASTA";
    if (type === "bgc_gbk_archive" || type === "bgc_bulk_archive") return "Download BGC archive";
    if (type === "structure_archive") return "Download structure archive";
    return "Download file";
  }

  function resourceAction(row) {
    const links = [];
    if (row.direct_download_url) {
      links.push(`<a class="btn btn-sm btn-primary" href="${html(row.direct_download_url)}" download="${html(row.filename || "")}">${html(downloadLabel(row))}</a>`);
    }
    return links.length ? links.join(" ") : '<span class="status-note">Direct download unavailable until public release validation is complete.</span>';
  }

  function renderResources(rows) {
    if (!rows.length) return '<p class="status-note">No verified public resource is mapped for this record.</p>';
    return `<ul class="related-list">${rows.map((row) => `
      <li>
        <strong>${html(row.filename || row.resource_type)}</strong>
        <span>${html(row.resource_type || "")}</span>
        ${row.release_version ? `<span>Release ${html(row.release_version)}</span>` : ""}
        ${row.validation_status ? `<span>${html(row.validation_status)}</span>` : ""}
        ${row.size_bytes ? `<span>${Number(row.size_bytes).toLocaleString()} bytes</span>` : ""}
        ${row.sha256 ? `<code>${html(row.sha256)}</code>` : ""}
        ${resourceAction(row)}
      </li>`).join("")}</ul>`;
  }

  function renderStructureViewer(resources, accession) {
    if (!config.viewerEnabled || config.entity !== "structures") return;
    const content = root.querySelector("[data-static-structure-content]");
    if (!content) return;
    const row = resources.find((item) => item.resource_type === "structure_cif" && item.browser_fetch_url);
    if (!row) {
      content.innerHTML = '<p class="status-note">Browser structure viewing is unavailable for this record. Use the verified CIF download link if available.</p>';
      return;
    }
    content.innerHTML = `
      <div id="viewer" class="structure-viewer static-structure-viewer" data-cif="${html(row.browser_fetch_url)}" data-accession="${html(accession)}">
        <div class="structure-loading">Loading predicted structure...</div>
      </div>
      <div class="viewer-controls" aria-label="Structure viewer controls">
        <button class="btn btn-sm btn-outline-primary" type="button" data-static-viewer-action="reset">Reset</button>
        <button class="btn btn-sm btn-outline-primary" type="button" data-static-viewer-action="spin">Spin</button>
        <button class="btn btn-sm btn-outline-primary" type="button" data-static-viewer-action="cartoon">Cartoon</button>
        <button class="btn btn-sm btn-outline-primary" type="button" data-static-viewer-action="surface">Surface</button>
      </div>`;
    if (window.StaticStructureViewer?.load) {
      window.StaticStructureViewer.load(content.querySelector("#viewer"), row.browser_fetch_url, accession);
    } else {
      content.querySelector("#viewer").innerHTML = '<div class="structure-error">The local structure viewer asset did not load. Use the CIF download link.</div>';
    }
  }

  async function run() {
    const id = (new URLSearchParams(location.search).get("id") || "").trim();
    if (!id) {
      renderMessage("Missing accession", `Add ?id=${config.prefix}000001 to the URL.`);
      return;
    }
    if (!new RegExp(config.pattern).test(id)) {
      renderMessage("Invalid accession", `${id} is not a supported ${config.prefix} accession.`);
      return;
    }
    if (config.unavailable) {
      renderMessage("Not present in this release", "Peptide records are not present in this release.");
      return;
    }
    const manifest = await fetch(config.accessionManifestUrl).then((response) => response.json());
    const entity = manifest[config.entity];
    const file = rangeFile(config.entity, id, entity);
    const shard = file ? entity.ranges.find((item) => item.file === file) : null;
    if (!shard) {
      renderMessage("Not found", `${id} has a valid format but is not present in this release.`);
      return;
    }
    const rows = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/${entity.detail_base}${shard.file}`).then((response) => response.json());
    const record = rows.find((row) => row.id === id);
    if (!record) {
      renderMessage("Not found", `${id} has a valid format but is not present in this release.`);
      return;
    }
    renderRecord(record);
  }

  run().catch(() => renderMessage("Unable to load record", "The static metadata shard could not be loaded."));
}());
