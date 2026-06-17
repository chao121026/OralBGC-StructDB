(function () {
  "use strict";

  const form = document.querySelector("[data-static-legacy]");
  const root = document.getElementById("static-legacy-root");
  const configEl = document.getElementById("static-legacy-config");
  if (!form || !root || !configEl) return;

  const config = JSON.parse(configEl.textContent);
  const html = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
  let manifestPromise = null;

  async function manifest() {
    if (!manifestPromise) {
      manifestPromise = fetch(config.manifestUrl).then((response) => response.json());
    }
    return manifestPromise;
  }

  async function legacyPartition(value) {
    const bytes = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest)).slice(0, 1).map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  async function resolve(value) {
    const id = value.trim();
    const normalized = id.toLowerCase();
    if (!id) {
      root.innerHTML = '<p class="status-note">Enter an exact legacy identifier.</p>';
      return;
    }
    const manifestData = await manifest();
    const prefix = await legacyPartition(normalized);
    const shard = (manifestData.shards || []).find((item) => item.prefix === prefix);
    const rows = shard ? await fetch(`${config.baseUrl.replace(/\/$/, "")}/${shard.file}`).then((response) => response.json()) : [];
    const match = rows.find((row) => row.normalized === normalized);
    if (!match) {
      root.innerHTML = `<p class="status-note">No exact match was found for <code>${html(id)}</code>.</p>`;
      return;
    }
    root.innerHTML = `<p class="status-note">Resolved to <a class="mono" href="${html(match.target)}">${html(match.public_accession)}</a>.</p>`;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    resolve(form.querySelector("input[name='id']").value);
  });
  const initial = new URLSearchParams(location.search).get("id");
  if (initial) {
    form.querySelector("input[name='id']").value = initial;
    resolve(initial);
  }
}());
