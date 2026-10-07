"""运行配置：端口、跨域、运行环境。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    app_name: str = "光伏电站运维管理平台"
    env: str = "local"
    port: int = 8000
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    page_size_default: int = 20
    page_size_max: int = 200
    # 运营概览：业务日切固定用 UTC+8，不跟服务器本地时区走，跨零点基数不再错位。
    business_tz_hours: int = 8
    # 汇总口径切换日期：之前的日期沿用旧口径（v1），当天及之后用统一新口径（v2）。
    overview_criteria_switch: str = "2026-10-07"
    # 汇总结果落库位置（相对 backend 目录）。
    summary_db_path: str = "data/overview_summary.db"


settings = Settings()
