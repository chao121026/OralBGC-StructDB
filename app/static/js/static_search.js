(function () {
  "use strict";

  const form = document.querySelector("[data-static-search]");
  if (!form) return;

  const config = JSON.parse(document.getElementById("static-search-config").textContent);
  let manifestPromise = null;
  const partitionCache = new Map();
  const postingsCache = new Map();
  const resultRoot = document.createElement("section");
  resultRoot.className = "section-subblock";
  resultRoot.setAttribute("aria-live", "polite");
  form.insertAdjacentElement("afterend", resultRoot);

  const html = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));

  function manifest() {
    if (!manifestPromise) {
      manifestPromise = fetch(config.manifestUrl).then((response) => response.json());
    }
    return manifestPromise;
  }

  function tokenFor(value) {
    return value.toLowerCase().split(/[^a-z0-9]+/).filter((token) => token.length >= 2);
  }

  async function loadTokenPartition(prefix, manifestData) {
    if (partitionCache.has(prefix)) return partitionCache.get(prefix);
    const partition = (manifestData.partitions || []).find((item) => item.prefix === prefix);
    if (!partition) {
      partitionCache.set(prefix, null);
      return null;
    }
    const manifestRows = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/${partition.file}`).then((response) => response.json());
    partitionCache.set(prefix, manifestRows);
    return manifestRows;
  }

  async function loadTokenPage(token, manifestData) {
    const prefix = token.slice(0, 2);
    const prefixManifest = await loadTokenPartition(prefix, manifestData);
    const entry = (prefixManifest?.tokens || []).find((item) => item.token === token);
    const page = entry?.pages?.[0];
    if (!page) return [];
    if (!postingsCache.has(page.file)) {
      const payload = await fetch(`${config.releaseBaseUrl.replace(/\/$/, "")}/${page.file}`).then((response) => response.json());
      postingsCache.set(page.file, payload.rows || []);
    }
    return postingsCache.get(page.file);
  }

  function render(rows, query, elapsedMs) {
    const limit = config.limit || 50;
    const shown = rows.slice(0, limit);
    resultRoot.innerHTML = `
      <h2>Search results <span class="muted">(${rows.length.toLocaleString()})</span></h2>
      <p class="status-note" role="status">${rows.length ? `Showing ${shown.length.toLocaleString()} of ${rows.length.toLocaleString()} matches in ${elapsedMs} ms.` : "No records matched this query."}</p>
      <ul class="related-list">
        ${shown.map((row) => `
          <li>
            <a class="mono" href="${html(row.url)}">${html(row.id)}</a>
            <span>${html(row.entity)} · ${html(row.label)}</span>
          </li>`).join("")}
      </ul>`;
  }

  async function runSearch() {
    const input = form.querySelector("input[name='q']");
    const query = (input && input.value || "").trim().toLowerCase();
    if (query.length < 2) {
      resultRoot.innerHTML = '<p class="status-note" role="status">Enter at least two characters.</p>';
      return;
    }
    resultRoot.innerHTML = '<p class="loading-state">Loading search index...</p>';
    const started = performance.now();
    const tokens = tokenFor(query);
    const manifestData = await manifest();
    const seenTokens = new Set(tokens);
    const matchesByRecord = new Map();
    for (const token of [...new Set(tokens)]) {
      for (const row of await loadTokenPage(token, manifestData)) {
        if (!seenTokens.has(row.token)) continue;
        const key = `${row.entity}:${row.id}`;
        const entry = matchesByRecord.get(key) || { row, tokens: new Set() };
        entry.tokens.add(row.token);
        matchesByRecord.set(key, entry);
      }
    }
    const matches = [...matchesByRecord.values()]
      .filter((entry) => tokens.every((token) => entry.tokens.has(token)))
      .map((entry) => entry.row);
    const elapsedMs = Math.round(performance.now() - started);
    window.ORALBGC_SEARCH_METRICS = {
      ...(window.ORALBGC_SEARCH_METRICS || {}),
      fetchedPartitions: new Set(tokens.map((token) => token.slice(0, 2))).size,
      lastQueryMs: elapsedMs,
      lastResultCount: matches.length,
    };
    render(matches, query, elapsedMs);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch();
  });
  form.querySelector("input[name='q']")?.addEventListener("focus", () => {
    manifest().catch(() => {
      resultRoot.innerHTML = '<p class="status-note" role="status">Search index could not be loaded.</p>';
    });
  }, { once: true });
  if (new URLSearchParams(location.search).get("q")) {
    runSearch();
  }
}());
