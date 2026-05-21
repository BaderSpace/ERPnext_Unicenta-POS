import os
from dataclasses import dataclass, field


@dataclass
class UnicentaDBConfig:
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "unicentaopos"


@dataclass
class ERPNextConfig:
    url: str = ""
    api_key: str = ""
    api_secret: str = ""


@dataclass
class SyncConfig:
    products: bool = True
    sales: bool = True
    product_direction: str = "unicenta_to_erpnext"
    sales_since_days: int = 7


@dataclass
class AppConfig:
    unicenta_db: UnicentaDBConfig = field(default_factory=UnicentaDBConfig)
    erpnext: ERPNextConfig = field(default_factory=ERPNextConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)


    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            unicenta_db=UnicentaDBConfig(
                host=os.getenv("UNICENTA_DB_HOST", "localhost"),
                port=int(os.getenv("UNICENTA_DB_PORT", "3306")),
                user=os.getenv("UNICENTA_DB_USER", "root"),
                password=os.getenv("UNICENTA_DB_PASSWORD", ""),
                database=os.getenv("UNICENTA_DB_NAME", "unicentaopos"),
            ),
            erpnext=ERPNextConfig(
                url=os.getenv("ERPNEXT_URL", "").rstrip("/"),
                api_key=os.getenv("ERPNEXT_API_KEY", ""),
                api_secret=os.getenv("ERPNEXT_API_SECRET", ""),
            ),
            sync=SyncConfig(
                products=os.getenv("SYNC_PRODUCTS", "true").lower() == "true",
                sales=os.getenv("SYNC_SALES", "true").lower() == "true",
                product_direction=os.getenv("PRODUCT_SYNC_DIRECTION", "unicenta_to_erpnext"),
                sales_since_days=int(os.getenv("SALES_SYNC_SINCE_DAYS", "7")),
            ),
        )
