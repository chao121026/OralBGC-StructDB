from functools import lru_cache
from pathlib import Path
import os


def _path_env(primary: str, fallback: str | None = None, default: str = "") -> Path:
    value = os.getenv(primary) or (os.getenv(fallback) if fallback else None) or default
    return Path(value)


class Settings:
    package_root: Path = _path_env("PHRC_BGCSTRUCTDB_DATA_ROOT", fallback="PACKAGE_ROOT", default="../PHRC_BGCStructDB_BGS_v1")
    db_path: Path = _path_env("DATABASE_PATH", default="app/data/phrc_bgcstructdb.sqlite")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "info")
    secret_key: str | None = os.getenv("SECRET_KEY")
    version: str = os.getenv("PHRC_VERSION", "PHRC_BGCStructDB_v1")
    contact_email: str = os.getenv("PHRC_CONTACT_EMAIL", "contact@example.edu")
    max_page_size: int = 100

    def resolve_db(self) -> Path:
        return self.db_path if self.db_path.is_absolute() else Path.cwd() / self.db_path

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
