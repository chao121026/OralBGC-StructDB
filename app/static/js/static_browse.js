(function () {
  "use strict";

  const roots = document.querySelectorAll("#static-browse-root");
  if (!roots.length) return;

  const text = (value) => String(value ?? "");
  const html = (value) => text(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));

  const columnsFor = (entity) => ({
    mags: [["id", "MAG"], ["original_mag_id", "Original ID"], ["bgc_count", "BGCs"], ["gcf_count", "GCFs"]],
    bgcs: [["id", "BGC"], ["mag", "MAG"], ["gcf", "GCF"], ["class", "Class"], ["protein_count", "Proteins"]],
    gcfs: [["id", "GCF"], ["class", "Class"], ["bgc_count", "BGCs"], ["mag_count", "MAGs"], ["protein_count", "Proteins"]],
    proteins: [["id", "Protein"], ["bgc", "BGC"], ["gcf", "GCF"], ["product", "Product"], ["gene", "Gene"], ["structure", "Structure"]],
    structures: [["id", "Structure"], ["protein", "Protein"], ["product", "Product"], ["mean_plddt", "Mean pLDDT"], ["compactness", "Compactness"], ["foldseek", "Foldseek/PDB"]],
  }[entity] || []);

  function queryToken(query) {
    return query.toLowerCase().split(/[^a-z0-9]+/).find((token) => token.length >= 3) || "";
  }

  function pageFile(pageSet, page) {
    const pages = pageSet?.pages || [];
    return pages[Math.max(0, Math.min(page - 1, pages.length - 1))];
  }

  async function fetchJson(state, relativeFile) {
    const key = relativeFile;
    if (!state.pageCache[key]) {
      const base = state.indexBaseUrl.replace(/\/$/, "");
      state.pageCache[key] = await fetch(`${base}/${relativeFile}`).then((response) => response.json());
    }
    return state.pageCache[key];
  }

  function resultSetFor(state) {
    const query = state.query.trim();
    if (query) {
      const token = queryToken(query);
      const entry = (state.manifest.browse_index.search.tokens || []).find((item) => item.token === token);
      return entry || { pages: [], record_count: 0 };
    }
    const columns = columnsFor(state.entity);
    const defaultSort = columns[0][0];
    if (state.sort === defaultSort && state.direction === "asc") {
      return state.manifest.browse_index.default_order;
    }
    return state.manifest.browse_index.sort_orders[`${state.sort}-${state.direction}`] || state.manifest.browse_index.default_order;
  }

  async function loadResultPage(state) {
    const resultSet = resultSetFor(state);
    const total = resultSet.record_count ?? resultSet.total ?? state.manifest.record_count;
    const uiPages = Math.max(1, Math.ceil(total / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), uiPages);
    const indexPageSize = resultSet.pages?.[0]?.record_count || state.manifest.browse_index.page_size || state.pageSize;
    const offset = (state.page - 1) * state.pageSize;
    const indexPageNumber = Math.floor(offset / indexPageSize) + 1;
    const page = pageFile(resultSet, indexPageNumber);
    if (!page) return { rows: [], total: 0, pages: 1 };
    const payload = await fetchJson(state, page.file);
    const rows = payload.rows || [];
    const start = offset % indexPageSize;
    return { rows: rows.slice(start, start + state.pageSize), total: payload.total ?? total, pages: uiPages };
  }

  async function render(root, state) {
    const columns = columnsFor(state.entity);
    const query = state.query.trim();
    const result = await loadResultPage(state);
    const total = result.total;
    const pages = result.pages;
    const pageRows = result.rows;
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (state.sort !== columns[0][0]) params.set("sort", state.sort);
    if (state.direction !== "asc") params.set("dir", state.direction);
    if (state.page !== 1) params.set("page", String(state.page));
    if (state.pageSize !== 25) params.set("page_size", String(state.pageSize));
    history.replaceState(null, "", `${location.pathname}${params.toString() ? `?${params}` : ""}`);

    root.innerHTML = `
      <section class="static-browse" aria-label="Static browse controls">
        <div class="filter-bar compact-filter">
          <label>Search <input data-role="query" value="${html(query)}" placeholder="identifier, class, product"></label>
          <label>Sort
            <select data-role="sort">${columns.map(([key, label]) => `<option value="${html(key)}"${key === state.sort ? " selected" : ""}>${html(label)}</option>`).join("")}</select>
          </label>
          <label>Direction
            <select data-role="direction"><option value="asc"${state.direction === "asc" ? " selected" : ""}>Ascending</option><option value="desc"${state.direction === "desc" ? " selected" : ""}>Descending</option></select>
          </label>
          <label>Page size
            <select data-role="page-size">${state.pageSizes.map((size) => `<option value="${size}"${size === state.pageSize ? " selected" : ""}>${size}</option>`).join("")}</select>
          </label>
          <button class="btn btn-light" type="button" data-role="reset">Clear</button>
        </div>
        <p class="status-note" role="status" tabindex="-1" data-role="status">${total ? `${total.toLocaleString()} records. Filters and sorts use precomputed global static indexes.` : "No records matched this query."}</p>
        <div class="table-responsive">
          <table class="table entity-table">
            <thead><tr>${columns.map(([, label]) => `<th scope="col">${html(label)}</th>`).join("")}</tr></thead>
            <tbody>${pageRows.map((row) => `<tr>${columns.map(([key], index) => {
              const value = html(row[key]);
              return `<td>${index === 0 && row.url ? `<a class="mono" href="${html(row.url)}">${value}</a>` : value}</td>`;
            }).join("")}</tr>`).join("")}</tbody>
          </table>
        </div>
        <nav class="pagination-controls" aria-label="Browse pagination">
          <button class="btn btn-outline-primary" type="button" data-role="prev"${state.page <= 1 ? " disabled" : ""}>Previous</button>
          <span>Page ${state.page.toLocaleString()} of ${pages.toLocaleString()}</span>
          <button class="btn btn-outline-primary" type="button" data-role="next"${state.page >= pages ? " disabled" : ""}>Next</button>
        </nav>
      </section>`;

    root.querySelector('[data-role="query"]').addEventListener("input", (event) => {
      state.query = event.target.value;
      state.page = 1;
      render(root, state);
    });
    root.querySelector('[data-role="sort"]').addEventListener("change", (event) => {
      state.sort = event.target.value;
      render(root, state);
    });
    root.querySelector('[data-role="direction"]').addEventListener("change", (event) => {
      state.direction = event.target.value;
      render(root, state);
    });
    root.querySelector('[data-role="page-size"]').addEventListener("change", (event) => {
      state.pageSize = Number(event.target.value);
      state.page = 1;
      render(root, state);
    });
    root.querySelector('[data-role="reset"]').addEventListener("click", () => {
      state.query = "";
      state.sort = columns[0][0];
      state.direction = "asc";
      state.pageSize = 25;
      state.page = 1;
      render(root, state);
    });
    root.querySelector('[data-role="prev"]').addEventListener("click", () => {
      state.page -= 1;
      render(root, state);
      root.querySelector('[data-role="status"]').focus();
    });
    root.querySelector('[data-role="next"]').addEventListener("click", () => {
      state.page += 1;
      render(root, state);
      root.querySelector('[data-role="status"]').focus();
    });
  }

  roots.forEach(async (root) => {
    const config = JSON.parse(document.getElementById("static-browse-config").textContent);
    const params = new URLSearchParams(location.search);
    root.innerHTML = '<p class="loading-state">Loading static index...</p>';
    let rows = [];
    let manifest = null;
    manifest = await fetch(config.manifestUrl).then((response) => response.json());
    const columns = columnsFor(config.entity);
    render(root, {
      entity: config.entity,
      pageSizes: config.pageSizes || [25, 50, 100],
      rows,
      manifest,
      browseBaseUrl: config.browseBaseUrl || "",
      indexBaseUrl: (config.manifestUrl || "").replace(/\/manifest\.json$/, ""),
      pageCache: {},
      query: params.get("q") || "",
      sort: params.get("sort") || columns[0][0],
      direction: params.get("dir") === "desc" ? "desc" : "asc",
      page: Number(params.get("page") || "1"),
      pageSize: Number(params.get("page_size") || "25"),
    });
  });
}());
