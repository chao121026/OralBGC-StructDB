from functools import lru_cache
from pathlib import Path
import os
from urllib.parse import urlparse


APP_ROOT = Path(__file__).resolve().parent


def _path_env(primary: str, fallback: str | None = None, default: str = "") -> Path:
    value = os.getenv(primary) or (os.getenv(fallback) if fallback else None) or default
    return Path(value)


class Settings:
    def __init__(self) -> None:
        self.package_root = _path_env("PHRC_BGCSTRUCTDB_DATA_ROOT", fallback="PACKAGE_ROOT", default="../PHRC_BGCStructDB_BGS_v1")
        self.db_path = _path_env("DATABASE_PATH", default="data/phrc_bgcstructdb.sqlite")
        self.manifest_path = _path_env(
            "INTEGRATED_RESOURCE_MANIFEST",
            default="data/integrated-resource-manifest.json",
        )
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.deployment_mode = os.getenv("DEPLOYMENT_MODE", "development")
        self.release_publication_state = os.getenv("RELEASE_PUBLICATION_STATE", "prepromotion")
        self.globus_direct_https_base_url = os.getenv("GLOBUS_DIRECT_HTTPS_BASE_URL", "https://g-f2d91c.6d8b.03c0.data.globus.org")
        self.globus_browser_fetch_base_url = os.getenv("GLOBUS_BROWSER_FETCH_BASE_URL", "https://g-f2d91c.6d8b.03c0.data.globus.org")
        self.globus_release_relative_root = os.getenv("GLOBUS_RELEASE_RELATIVE_ROOT", "releases/v1")
        self.globus_allowed_hosts = tuple(
            host.strip()
            for host in os.getenv("GLOBUS_ALLOWED_HOSTS", "g-f2d91c.6d8b.03c0.data.globus.org").split(",")
            if host.strip()
        )
        self.log_level = os.getenv("LOG_LEVEL", "info")
        self.secret_key = os.getenv("SECRET_KEY")
        self.version = os.getenv("PHRC_VERSION", "PHRC_BGCStructDB_v1")
        self.contact_email = os.getenv("PHRC_CONTACT_EMAIL", "jz7982@nyu.edu")
        self.max_page_size = 100
        self.public_name = os.getenv("DATABASE_PUBLIC_NAME", "OralBGC-StructDB")
        self.subtitle = os.getenv(
            "DATABASE_SUBTITLE",
            "A structure-enabled database of biosynthetic gene cluster proteins from the oral microbiome",
        )
        self.institution = os.getenv(
            "DATABASE_INSTITUTION",
            "Public Health Research Center, New York University Abu Dhabi",
        )
        self.institution_short = os.getenv(
            "DATABASE_INSTITUTION_SHORT",
            "Public Health Research Center, NYU Abu Dhabi",
        )
        self.institution_url = os.getenv(
            "DATABASE_INSTITUTION_URL",
            "https://nyuad.nyu.edu/en/research/faculty-labs-and-projects/public-health-research-center.html",
        )
        self.public_release_label = os.getenv("DATABASE_PUBLIC_RELEASE_LABEL", "v1")
        self.bigscape_max_nodes = int(os.getenv("BIGSCAPE_MAX_NODES", "2000"))
        self.bigscape_max_edges = int(os.getenv("BIGSCAPE_MAX_EDGES", "10000"))
        self.bigscape_max_json_bytes = int(os.getenv("BIGSCAPE_MAX_JSON_BYTES", str(10 * 1024 * 1024)))

    def resolve_db(self) -> Path:
        return self.db_path if self.db_path.is_absolute() else APP_ROOT / self.db_path

    def resolve_manifest(self) -> Path:
        return self.manifest_path if self.manifest_path.is_absolute() else APP_ROOT / self.manifest_path

    def resolve_package_root(self) -> Path:
        return self.package_root if self.package_root.is_absolute() else (Path.cwd() / self.package_root).resolve()

    def required_release_files(self) -> list[Path]:
        root = self.resolve_package_root()
        return [
            root / "metadata" / "BGS_public_accession_mapping.tsv",
            root / "metadata" / "tables" / "PHRC_integrated_BGC_protein_structure_summary.tsv",
            root / "sequences" / "BGS_BGC_proteins_v1.0.faa",
            root / "antismash" / "BGS_BGC_GBK_v1.0.tar.gz",
            root / "manifests" / "public_file_manifest.tsv",
        ]

    def validate_release_root(self) -> None:
        missing = [path for path in self.required_release_files() if not path.exists()]
        if missing:
            formatted = ", ".join(path.as_posix() for path in missing)
            raise RuntimeError(f"Configured PHRC/BGS release root is missing required files: {formatted}")

    def validate_resource_delivery(self) -> None:
        if self.release_publication_state not in {"prepromotion", "staging_validation", "published"}:
            raise RuntimeError("RELEASE_PUBLICATION_STATE must be prepromotion, staging_validation, or published")
        if self.deployment_mode not in {"development", "editor_preview", "production", "published"}:
            raise RuntimeError("DEPLOYMENT_MODE must be development, editor_preview, production, or published")
        root = self.globus_release_relative_root.strip("/")
        if not root or ".." in root or "\\" in root or "?" in root or "#" in root:
            raise RuntimeError("GLOBUS_RELEASE_RELATIVE_ROOT is unsafe")
        for base in [self.globus_direct_https_base_url, self.globus_browser_fetch_base_url]:
            if not base:
                continue
            parsed = urlparse(base)
            if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
                raise RuntimeError("Globus direct HTTPS bases must be clean HTTPS origins")
            allowed = self.globus_allowed_hosts or (parsed.netloc,)
            if parsed.netloc not in allowed or parsed.netloc == "app.globus.org":
                raise RuntimeError("Globus direct HTTPS host is not allowlisted")

    @property
    def branding(self) -> dict[str, str]:
        return {
            "public_name": self.public_name,
            "subtitle": self.subtitle,
            "institution": self.institution,
            "institution_short": self.institution_short,
            "institution_url": self.institution_url,
            "public_release_label": self.public_release_label,
            "contact_email": self.contact_email,
        }

    @property
    def preview_message(self) -> str | None:
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
