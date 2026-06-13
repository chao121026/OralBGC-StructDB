from functools import lru_cache
from pathlib import Path
import os

class Settings:
    package_root: Path = Path(os.getenv("PHRC_PACKAGE_ROOT", "/Users/jz7982/Documents/PHRC_BGCStructDB_v1"))
    db_path: Path = Path(os.getenv("PHRC_DB_PATH", "app/data/phrc_bgcstructdb.sqlite"))
    version: str = os.getenv("PHRC_VERSION", "PHRC_BGCStructDB_v1")
    contact_email: str = os.getenv("PHRC_CONTACT_EMAIL", "contact@example.edu")
    max_page_size: int = 100

    def resolve_db(self) -> Path:
        return self.db_path if self.db_path.is_absolute() else Path.cwd() / self.db_path

@lru_cache
def get_settings() -> Settings:
    return Settings()
