"""运营概览汇总口径：全平台只有这一份，卡片、模块统计、明细、落库都从这里出数。

统一口径（v2，2026-10-07 起）：
- 待处理：按状态推导——告警未消除、缺陷未关闭，不信记录里残留的 pending 标记；
- 异常量：只算未闭环的告警（未消除）和未验收的缺陷（未验收也未关闭）；
- 今日新增：业务日期（固定 UTC+8 日切）等于统计日期的告警/缺陷，跨零点基数不再错位；
- 概览按片区列出待处理量与异常量，卡片由各片区行汇总得出，两处读同一份落库数据；
- 两处口径打架时以概览为准。

历史口径（v1，2026-10-07 之前）：沿用旧的统计方式（读记录上的 pending/abnormal 标记），
已生成的历史概览不按新口径重算；重算只作用于口径调整之后的日期。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.store import store
from app.summary_store import summary_store

# 参与运营概览汇总的业务模块：告警事件 + 缺陷管理。
SUMMARY_MODULES = ("alarm", "defect")
DATE_FIELDS = {"alarm": "触发时间", "defect": "发现日期"}
REGION_FIELD = "所属片区"
DEFAULT_REGION = "未分区"

# 状态终态：告警闭环 = 已消除；缺陷验收 = 已验收/已关闭。
ALARM_CLOSED_STATUS = "已消除"
DEFECT_FINAL_STATUS = "已关闭"
DEFECT_ACCEPTED_STATUSES = ("已验收", "已关闭")

CRITERIA_SWITCH = date.fromisoformat(settings.overview_criteria_switch)
BUSINESS_TZ = timezone(timedelta(hours=settings.business_tz_hours))

CRITERIA_NOTES = {
    1: "旧口径：按记录标记统计（历史沿用，未按新口径重算）",
    2: "新口径：异常量只算未闭环告警与未验收缺陷",
}


def business_today() -> date:
    """业务日切固定 UTC+8，不跟服务器本地时区走。"""
    return datetime.now(BUSINESS_TZ).date()


def criteria_version_for(day: date) -> int:
    """口径调整之前的日期沿用旧口径，调整当天及之后用新口径。"""
    return 2 if day >= CRITERIA_SWITCH else 1


def _parse_day(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _region_of(row: dict[str, Any]) -> str:
    return str(row.get(REGION_FIELD) or "").strip() or DEFAULT_REGION


def _kinds_for(row: dict[str, Any], module: str, day: date, version: int) -> list[str]:
    """单条记录命中哪些汇总口径：待处理 / 异常量 / 当日新增。"""
    status = str(row.get("status") or "")
    if version >= 2:
        if module == "alarm":
            pending = status != ALARM_CLOSED_STATUS
            abnormal = status != ALARM_CLOSED_STATUS
        else:
            pending = status != DEFECT_FINAL_STATUS
            abnormal = status not in DEFECT_ACCEPTED_STATUSES
    else:
        pending = bool(row.get("pending"))
        abnormal = bool(row.get("abnormal"))
    created = _parse_day(row.get(DATE_FIELDS[module])) == day
    kinds = []
    if pending:
        kinds.append("pending")
    if abnormal:
        kinds.append("abnormal")
    if created:
        kinds.append("created")
    return kinds


class OverviewService:
    """汇总编排：算口径、落库、回填、给卡片和模块统计供数。"""

    # ---- 汇总计算 ----

    def _build_snapshots(self, day: date) -> list[dict[str, Any]]:
        """按当前业务数据为指定日期生成各片区快照（不落库，落库由调用方决定）。"""
        version = criteria_version_for(day)
        generated_at = datetime.now(BUSINESS_TZ).isoformat(timespec="seconds")
        regions = sorted(
            {_region_of(row) for module in SUMMARY_MODULES for row in store.rows(module)}
        )
        snapshots = []
        for region in regions:
            details: list[dict[str, Any]] = []
            for module in SUMMARY_MODULES:
                for row in store.rows(module):
                    if _region_of(row) != region:
                        continue
                    kinds = _kinds_for(row, module, day, version)
                    if not kinds:
                        continue
                    details.append({
                        "module": module,
                        "id": row.get("id"),
                        "kinds": kinds,
                        "fields": dict(row),
                    })
            snapshots.append({
                "summary_date": day.isoformat(),
                "region": region,
                "criteria_version": version,
                "pending": sum(1 for item in details if "pending" in item["kinds"]),
                "abnormal": sum(1 for item in details if "abnormal" in item["kinds"]),
                "created": sum(1 for item in details if "created" in item["kinds"]),
                "details": details,
                "generated_at": generated_at,
            })
        return snapshots

    @staticmethod
    def _module_counts(details: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        for module in SUMMARY_MODULES:
            module_details = [item for item in details if item["module"] == module]
            counts[module] = {
                "pending": sum(1 for item in module_details if "pending" in item["kinds"]),
                "abnormal": sum(1 for item in module_details if "abnormal" in item["kinds"]),
                "created": sum(1 for item in module_details if "created" in item["kinds"]),
            }
        return counts

    def _assemble(self, day: date, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        regions = []
        for snap in snapshots:
            module_counts = self._module_counts(snap.get("details") or [])
            regions.append({
                "region": snap["region"],
                "created": snap["created"],
                "pending": snap["pending"],
                "abnormal": snap["abnormal"],
                "alarm_pending": module_counts["alarm"]["pending"],
                "alarm_abnormal": module_counts["alarm"]["abnormal"],
                "defect_pending": module_counts["defect"]["pending"],
                "defect_abnormal": module_counts["defect"]["abnormal"],
            })
        version = criteria_version_for(day)
        created_label = "今日新增" if day == business_today() else "当日新增"
        cards = [
            {"label": "覆盖片区", "value": len(regions)},
            {"label": created_label, "value": sum(row["created"] for row in regions)},
            {"label": "待处理", "value": sum(row["pending"] for row in regions)},
            {"label": "异常量", "value": sum(row["abnormal"] for row in regions)},
        ]
        generated_at = max((str(snap.get("generated_at") or "") for snap in snapshots), default="")
        return {
            "date": day.isoformat(),
            "criteria_version": version,
            "criteria_note": CRITERIA_NOTES[version],
            "generated_at": generated_at,
            "cards": cards,
            "regions": regions,
        }

    # ---- 对外读数 ----

    def get_overview(self, day: date | None = None) -> dict[str, Any]:
        """读取某天的运营概览；当天实时重算并落库，历史日期以落库快照为准。"""
        day = day or business_today()
        if day >= business_today():
            # 当天（及以后）：实时重算、整天替换落库，同一片区一天只留最新一版。
            summary_store.replace_day(day.isoformat(), self._build_snapshots(day))
        elif not summary_store.fetch(day.isoformat()):
            # 历史日期缺快照时按当天日期适用的口径补齐，已存在的概览不重算。
            for snapshot in self._build_snapshots(day):
                summary_store.insert_missing(snapshot)
        return self._assemble(day, summary_store.fetch(day.isoformat()))

    def get_details(self, day: date, region: str) -> dict[str, Any] | None:
        """明细与卡片读同一份落库快照，落库后两处不会对不上。"""
        self.get_overview(day)
        snapshot = summary_store.fetch_one(day.isoformat(), region)
        if snapshot is None:
            return None
        return {
            "date": snapshot["summary_date"],
            "region": snapshot["region"],
            "criteria_version": snapshot["criteria_version"],
            "criteria_note": CRITERIA_NOTES[snapshot["criteria_version"]],
            "generated_at": snapshot["generated_at"],
            "counts": {
                "pending": snapshot["pending"],
                "abnormal": snapshot["abnormal"],
                "created": snapshot["created"],
            },
            "entries": snapshot["details"],
        }

    def module_stats(self, module: str) -> dict[str, Any]:
        """告警/缺陷列表页的统计卡片：与运营概览读同一份落库汇总。"""
        day = business_today()
        self.get_overview(day)
        details = [
            item
            for snapshot in summary_store.fetch(day.isoformat())
            for item in snapshot["details"]
            if item["module"] == module
        ]
        if module == "alarm":
            stats = [
                {"label": "未确认告警", "value": sum(1 for item in details if item["fields"].get("status") == "未确认")},
                {"label": "今日新增告警", "value": sum(1 for item in details if "created" in item["kinds"])},
                {"label": "未消除告警", "value": sum(1 for item in details if "pending" in item["kinds"])},
            ]
        else:
            stats = [
                {"label": "待处理缺陷", "value": sum(1 for item in details if "pending" in item["kinds"])},
                {"label": "处理中缺陷", "value": sum(1 for item in details if item["fields"].get("status") == "处理中")},
                {"label": "超期缺陷", "value": sum(
                    1 for item in details
                    if "pending" in item["kinds"]
                    and (deadline := _parse_day(item["fields"].get("整改时限"))) is not None
                    and deadline < day
                )},
            ]
        return {"date": day.isoformat(), "module": module, "stats": stats}

    # ---- 存量回填 ----

    def backfill(self) -> dict[str, Any]:
        """存量汇总按月份回填：只补缺不覆盖，历史概览沿用原有口径。

        覆盖业务数据里出现过的、今天之前的每一个统计日期 × 每一个片区；
        当天及以后的汇总由读取时实时生成，不在回填范围。
        """
        today = business_today()
        days = sorted(
            {
                day
                for module in SUMMARY_MODULES
                for row in store.rows(module)
                if (day := _parse_day(row.get(DATE_FIELDS[module]))) is not None
                and day < today
            }
        )
        months: dict[str, dict[str, int]] = {}
        for day in days:
            month_key = day.strftime("%Y-%m")
            bucket = months.setdefault(month_key, {"inserted": 0, "skipped": 0})
            for snapshot in self._build_snapshots(day):
                if summary_store.insert_missing(snapshot):
                    bucket["inserted"] += 1
                else:
                    bucket["skipped"] += 1
        report = [{"month": key, **months[key]} for key in sorted(months)]
        total_inserted = sum(item["inserted"] for item in report)
        return {
            "ok": True,
            "message": f"存量汇总已按月份回填：新增 {total_inserted} 条，已存在的保持原口径不动",
            "months": report,
        }


overview_service = OverviewService()
