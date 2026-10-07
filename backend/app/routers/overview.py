"""运营概览接口：统一汇总口径的读数、明细钻取与存量回填。

口径规则全部收在 app.services.overview，路由层只做参数解析；
卡片、明细、模块统计三处读的是同一份落库快照，口径打架时以概览为准。
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.services.overview import overview_service
from app.summary_store import summary_store

router = APIRouter(prefix="/api/overview", tags=["运营概览"])


def _parse_date(raw: str | None, label: str = "统计日期") -> date:
    if not raw:
        raise HTTPException(status_code=400, detail=f"缺少{label}，格式应为 YYYY-MM-DD")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}「{raw}」不是合法日期，格式应为 YYYY-MM-DD") from None


@router.get("")
def get_overview(day: str | None = Query(default=None, description="统计日期，默认今天（UTC+8 业务日切）")) -> dict:
    """运营概览：卡片与片区行都出自落库快照；历史日期沿用生成时的口径，不按新口径重算。"""
    target = _parse_date(day) if day else None
    return overview_service.get_overview(target)


@router.get("/details")
def get_details(
    day: str = Query(..., description="统计日期 YYYY-MM-DD"),
    region: str = Query(..., description="片区名称"),
) -> dict:
    """某个片区某天的汇总明细：与卡片读同一份落库数据，点进来看到的就是卡片里数的那些。"""
    target = _parse_date(day)
    detail = overview_service.get_details(target, region)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"{target.isoformat()} 片区「{region}」没有已落库的汇总")
    return detail


@router.get("/snapshots")
def list_snapshots(month: str | None = Query(default=None, description="按月份过滤，格式 YYYY-MM")) -> dict:
    """已落库的汇总清单：用来核对历史概览及其生成口径。"""
    items = summary_store.list_snapshots(month)
    return {"month": month, "total": len(items), "items": items}


@router.post("/backfill")
def backfill() -> dict:
    """存量汇总按月份回填：只补缺、不覆盖，已生成的历史概览保持原口径。"""
    return overview_service.backfill()
