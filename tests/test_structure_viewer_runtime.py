import json
import subprocess
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
VIEWER_JS = ROOT / "app/static/js/structure.js"
FIXTURE_CIF = ROOT / "tests/fixtures/minimal_structure.cif"


def run_viewer_case(case: str) -> dict:
    script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const source = fs.readFileSync({str(VIEWER_JS)!r}, 'utf8');
        const cif = fs.readFileSync({str(FIXTURE_CIF)!r}, 'utf8');

        const logs = [];
        const element = {{
          dataset: {{ cif: 'https://downloads.example.test/staging/v1/structures/cif/structures/BGS-STR-000001.cif' }},
          classList: {{
            values: new Set(),
            add(value) {{ this.values.add(value); }},
            remove(value) {{ this.values.delete(value); }},
            contains(value) {{ return this.values.has(value); }},
          }},
          innerHTML: '<div class="structure-loading">Loading 3D structure...</div>',
          textContent: '',
          insertAdjacentHTML(position, html) {{ this.innerHTML += html; }},
          querySelectorAll() {{ return []; }},
        }};
        const controls = {{ addEventListener() {{}} }};
        const document = {{
          addEventListener() {{}},
          getElementById(id) {{ return id === 'viewer' ? element : null; }},
          querySelector(selector) {{ return selector === '.viewer-controls' ? controls : null; }},
        }};
        const model = {{
          selectedAtoms() {{
            if ({case!r} === 'empty-model') return [];
            return [{{ serial: 1 }}, {{ serial: 2 }}];
          }},
        }};
        const viewer = {{
          models: [model],
          addModel(text, parser) {{
            logs.push(['addModel', parser, text.slice(0, 9)]);
            if ({case!r} === 'parse-failure') throw new Error('parse failed');
            return model;
          }},
          setStyle() {{ logs.push(['setStyle']); }},
          removeAllSurfaces() {{ logs.push(['removeAllSurfaces']); }},
          zoomTo() {{ logs.push(['zoomTo']); }},
          zoom() {{}},
          center() {{}},
          render() {{ logs.push(['render']); }},
          resize() {{}},
          spin() {{}},
        }};
        const response = {{
          ok: {str(case != "http-error").lower()},
          status: {500 if case == "http-error" else 200},
          text: async () => {{
            if ({case!r} === 'empty-response') return '';
            if ({case!r} === 'html-response') return '<html>login</html>';
            return cif;
          }},
        }};
        const fetch = async (url, options) => {{
          logs.push(['fetch', url, options.method, options.mode, options.credentials, options.cache]);
          return response;
        }};
        const context = {{
          window: {{}},
          document,
          console: {{ error: (...args) => logs.push(['console.error', ...args.map(String)]) }},
          fetch,
          requestAnimationFrame: (callback) => callback(),
          cancelAnimationFrame() {{}},
          setTimeout: (callback) => callback(),
        }};
        context.window.$3Dmol = {{
          createViewer(target, options) {{
            logs.push(['createViewer', options.backgroundColor]);
            return viewer;
          }},
          SurfaceType: {{ VDW: 'VDW' }},
        }};
        context.$3Dmol = context.window.$3Dmol;

        vm.createContext(context);
        vm.runInContext(source, context);

        (async () => {{
          const api = context.window.StaticStructureViewer;
          if (!api) {{
            console.log(JSON.stringify({{ missingApi: true, logs }}));
            return;
          }}
          await api.loadStructureViewer(element);
          console.log(JSON.stringify({{
            missingApi: false,
            logs,
            innerHTML: element.innerHTML,
            ready: element.classList.contains('structure-ready'),
            error: element.classList.contains('structure-error-state'),
            status: element.dataset.viewerStatus || null,
            errorCategory: element.dataset.viewerError || null,
          }}));
        }})().catch((error) => {{
          console.log(JSON.stringify({{ uncaught: error.message, logs }}));
        }});
        """
    )
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_structure_detail_uses_manifest_url_and_preserves_download(monkeypatch):
    monkeypatch.setenv("GLOBUS_RELEASE_RELATIVE_ROOT", "staging/v1")
    get_settings.cache_clear()
    response = TestClient(app).get("/structures/BGS-STR-000001")
    get_settings.cache_clear()

    expected = "https://g-f2d91c.6d8b.03c0.data.globus.org/staging/v1/structures/cif/structures/BGS-STR-000001.cif"
    assert response.status_code == 200
    assert f'data-cif="{expected}"' in response.text
    assert f'href="{expected}"' in response.text
    assert response.text.index("3Dmol-min.js") < response.text.index("js/structure.js")
    assert "app.globus.org" not in response.text


def test_structure_viewer_loads_cif_with_nonempty_model():
    result = run_viewer_case("success")

    assert result["missingApi"] is False
    assert ["fetch", "https://downloads.example.test/staging/v1/structures/cif/structures/BGS-STR-000001.cif", "GET", "cors", "omit", "no-store"] in result["logs"]
    assert ["addModel", "cif", "data_test"] in result["logs"]
    assert ["render"] in result["logs"]
    assert result["ready"] is True
    assert result["status"] == "loaded"


def test_structure_viewer_reports_controlled_failures():
    expected = {
        "http-error": "http-error",
        "empty-response": "empty-response",
        "html-response": "html-response",
        "parse-failure": "cif-parse-error",
        "empty-model": "empty-model",
    }

    for case, category in expected.items():
        result = run_viewer_case(case)
        assert result["ready"] is False
        assert result["error"] is True
        assert result["errorCategory"] == category
        assert "Structure could not be loaded." in result["innerHTML"]
        assert "Download the CIF file instead." in result["innerHTML"]
