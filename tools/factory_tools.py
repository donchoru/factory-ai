"""공장 생산 데이터 조회 도구 — 8개 @tool."""
import json
from langchain_core.tools import tool
from db.connection import query


@tool
def get_daily_production(
    line: str = "",
    model: str = "",
    date_from: str = "",
    date_to: str = "",
    shift: str = "",
) -> str:
    """일별 생산 실적 조회. 라인/모델/날짜범위/교대로 필터링 가능.

    Args:
        line: 라인 ID (LINE-1, LINE-2, LINE-3). 빈 문자열이면 전체.
        model: 모델 ID (SONATA, TUCSON, GV70, IONIQ6). 빈 문자열이면 전체.
        date_from: 시작일 (YYYY-MM-DD). 빈 문자열이면 전체 기간.
        date_to: 종료일 (YYYY-MM-DD). 빈 문자열이면 전체 기간.
        shift: 교대 ID (DAY, NIGHT, MIDNIGHT). 빈 문자열이면 전체.
    """
    sql = "SELECT * FROM daily_production WHERE 1=1"
    params = []

    if line:
        sql += " AND line_id = ?"
        params.append(line)
    if model:
        sql += " AND model_id = ?"
        params.append(model)
    if date_from:
        sql += " AND production_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND production_date <= ?"
        params.append(date_to)
    if shift:
        sql += " AND shift_id = ?"
        params.append(shift)

    sql += " ORDER BY production_date, line_id, shift_id"
    rows = query(sql, tuple(params))
    return json.dumps(rows, ensure_ascii=False)


@tool
def get_production_summary(
    period: str = "this_month",
    line: str = "",
    model: str = "",
) -> str:
    """기간별 생산 요약 — 라인별, 모델별 합계와 달성률.

    Args:
        period: 기간 (today, this_week, this_month). 기본값 this_month.
        line: 라인 ID (LINE-1, LINE-2, LINE-3). 빈 문자열이면 전체.
        model: 모델 ID (SONATA, TUCSON, GV70, IONIQ6). 빈 문자열이면 전체.
    """
    if period == "today":
        date_filter = "production_date = '2026-02-28'"
    elif period == "this_week":
        date_filter = "production_date >= '2026-02-23' AND production_date <= '2026-02-28'"
    else:
        date_filter = "production_date >= '2026-02-01' AND production_date <= '2026-02-28'"

    line_filter = ""
    model_filter = ""
    if line:
        line_filter = f" AND p.line_id = '{line}'"
    if model:
        model_filter = f" AND p.model_id = '{model}'"

    # 라인별 요약
    line_sql = f"""
        SELECT p.line_id, pl.line_name,
               SUM(p.planned_qty) as total_planned,
               SUM(p.actual_qty) as total_actual,
               SUM(p.defect_qty) as total_defects,
               ROUND(SUM(p.actual_qty) * 100.0 / NULLIF(SUM(p.planned_qty), 0), 1) as achievement_rate,
               ROUND(SUM(p.defect_qty) * 100.0 / NULLIF(SUM(p.planned_qty), 0), 2) as defect_rate
        FROM daily_production p
        JOIN production_lines pl ON p.line_id = pl.line_id
        WHERE {date_filter}{line_filter}{model_filter}
        GROUP BY p.line_id
        ORDER BY p.line_id
    """
    line_rows = query(line_sql)

    # 모델별 요약
    model_sql = f"""
        SELECT p.model_id, m.model_name, p.line_id,
               SUM(p.planned_qty) as total_planned,
               SUM(p.actual_qty) as total_actual,
               SUM(p.defect_qty) as total_defects,
               ROUND(SUM(p.actual_qty) * 100.0 / NULLIF(SUM(p.planned_qty), 0), 1) as achievement_rate
        FROM daily_production p
        JOIN models m ON p.model_id = m.model_id
        WHERE {date_filter}{line_filter}{model_filter}
        GROUP BY p.model_id
        ORDER BY total_actual DESC
    """
    model_rows = query(model_sql)

    result = {
        "period": period,
        "by_line": line_rows,
        "by_model": model_rows,
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def get_defect_stats(
    line: str = "",
    model: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """불량 통계 — 유형별 집계 + 라인/모델별 불량률.

    Args:
        line: 라인 ID. 빈 문자열이면 전체.
        model: 모델 ID. 빈 문자열이면 전체.
        date_from: 시작일. 빈 문자열이면 전체 기간.
        date_to: 종료일. 빈 문자열이면 전체 기간.
    """
    where = "WHERE 1=1"
    params = []
    if line:
        where += " AND d.line_id = ?"
        params.append(line)
    if model:
        where += " AND d.model_id = ?"
        params.append(model)
    if date_from:
        where += " AND d.production_date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND d.production_date <= ?"
        params.append(date_to)

    # 유형별 집계
    type_sql = f"""
        SELECT d.defect_type, SUM(d.defect_count) as total_count,
               COUNT(DISTINCT d.production_date) as affected_days
        FROM defects d
        {where}
        GROUP BY d.defect_type
        ORDER BY total_count DESC
    """
    type_rows = query(type_sql, tuple(params))

    # 라인별 불량률
    rate_sql = f"""
        SELECT d.line_id, SUM(d.defect_count) as total_defects,
               (SELECT SUM(actual_qty) FROM daily_production p
                WHERE p.line_id = d.line_id
                {'AND p.production_date >= ?' if date_from else ''}
                {'AND p.production_date <= ?' if date_to else ''}) as total_produced,
               ROUND(SUM(d.defect_count) * 100.0 /
                     NULLIF((SELECT SUM(actual_qty) FROM daily_production p
                             WHERE p.line_id = d.line_id
                             {'AND p.production_date >= ?' if date_from else ''}
                             {'AND p.production_date <= ?' if date_to else ''}), 0), 2) as defect_rate
        FROM defects d
        {where}
        GROUP BY d.line_id
        ORDER BY defect_rate DESC
    """
    rate_params = list(params)
    for _ in range(2):  # 서브쿼리 파라미터
        if date_from:
            rate_params.append(date_from)
        if date_to:
            rate_params.append(date_to)
    rate_rows = query(rate_sql, tuple(rate_params))

    # 최근 불량 상세 (최대 10건)
    recent_sql = f"""
        SELECT d.production_date, d.line_id, d.model_id, d.shift_id,
               d.defect_type, d.defect_count, d.description
        FROM defects d
        {where}
        ORDER BY d.production_date DESC, d.defect_count DESC
        LIMIT 10
    """
    recent_rows = query(recent_sql, tuple(params))

    result = {
        "by_type": type_rows,
        "by_line": rate_rows,
        "recent_defects": recent_rows,
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def get_line_status(line: str = "") -> str:
    """라인 현황 — 라인 정보 + 최근 달성률 + 가동 상태.

    Args:
        line: 라인 ID. 빈 문자열이면 전체 라인.
    """
    where = ""
    params = []
    if line:
        where = "WHERE pl.line_id = ?"
        params.append(line)

    sql = f"""
        SELECT pl.line_id, pl.line_name, pl.vehicle_type, pl.capacity_per_shift, pl.status,
               (SELECT ROUND(AVG(achievement_rate), 1) FROM daily_production
                WHERE line_id = pl.line_id AND production_date >= '2026-02-22') as recent_achievement,
               (SELECT SUM(actual_qty) FROM daily_production
                WHERE line_id = pl.line_id AND production_date = '2026-02-28') as today_actual,
               (SELECT SUM(planned_qty) FROM daily_production
                WHERE line_id = pl.line_id AND production_date = '2026-02-28') as today_planned,
               (SELECT COUNT(*) FROM downtime
                WHERE line_id = pl.line_id AND start_datetime >= '2026-02-22') as recent_downtime_count,
               (SELECT ROUND(SUM(defect_qty) * 100.0 / NULLIF(SUM(actual_qty), 0), 2)
                FROM daily_production
                WHERE line_id = pl.line_id AND production_date >= '2026-02-22') as recent_defect_rate
        FROM production_lines pl
        {where}
        ORDER BY pl.line_id
    """
    rows = query(sql, tuple(params))
    return json.dumps(rows, ensure_ascii=False)


@tool
def get_downtime_history(
    line: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """설비 정지 이력 — 정지 사유별 분류 + 상세 내역.

    Args:
        line: 라인 ID. 빈 문자열이면 전체.
        date_from: 시작일. 빈 문자열이면 전체 기간.
        date_to: 종료일. 빈 문자열이면 전체 기간.
    """
    where = "WHERE 1=1"
    params = []
    if line:
        where += " AND line_id = ?"
        params.append(line)
    if date_from:
        where += " AND start_datetime >= ?"
        params.append(date_from)
    if date_to:
        where += " AND end_datetime <= ?"
        params.append(date_to + "T23:59")

    # 사유별 집계
    summary_sql = f"""
        SELECT reason_type, COUNT(*) as count,
               SUM(duration_minutes) as total_minutes,
               ROUND(AVG(duration_minutes), 0) as avg_minutes
        FROM downtime
        {where}
        GROUP BY reason_type
        ORDER BY total_minutes DESC
    """
    summary_rows = query(summary_sql, tuple(params))

    # 상세 내역
    detail_sql = f"""
        SELECT line_id, start_datetime, end_datetime,
               duration_minutes, reason_type, description
        FROM downtime
        {where}
        ORDER BY start_datetime DESC
    """
    detail_rows = query(detail_sql, tuple(params))

    result = {
        "summary": summary_rows,
        "details": detail_rows,
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def get_model_comparison(
    date_from: str = "2026-02-01",
    date_to: str = "2026-02-28",
) -> str:
    """차종별 생산 비교 — 모델 간 생산량, 달성률, 불량률 비교.

    Args:
        date_from: 시작일. 기본값 2026-02-01.
        date_to: 종료일. 기본값 2026-02-28.
    """
    sql = """
        SELECT p.model_id, m.model_name, m.line_id,
               COUNT(DISTINCT p.production_date) as working_days,
               SUM(p.planned_qty) as total_planned,
               SUM(p.actual_qty) as total_actual,
               SUM(p.defect_qty) as total_defects,
               ROUND(SUM(p.actual_qty) * 100.0 / NULLIF(SUM(p.planned_qty), 0), 1) as achievement_rate,
               ROUND(SUM(p.defect_qty) * 100.0 / NULLIF(SUM(p.actual_qty), 0), 2) as defect_rate,
               ROUND(SUM(p.actual_qty) * 1.0 / COUNT(DISTINCT p.production_date), 0) as daily_avg
        FROM daily_production p
        JOIN models m ON p.model_id = m.model_id
        WHERE p.production_date >= ? AND p.production_date <= ?
        GROUP BY p.model_id
        ORDER BY total_actual DESC
    """
    rows = query(sql, (date_from, date_to))
    return json.dumps(rows, ensure_ascii=False)


@tool
def get_shift_analysis(
    line: str = "",
    date_from: str = "2026-02-01",
    date_to: str = "2026-02-28",
) -> str:
    """교대별 생산 분석 — 교대 간 생산량, 달성률, 불량률 비교.

    Args:
        line: 라인 ID. 빈 문자열이면 전체.
        date_from: 시작일. 기본값 2026-02-01.
        date_to: 종료일. 기본값 2026-02-28.
    """
    where = "WHERE p.production_date >= ? AND p.production_date <= ?"
    params = [date_from, date_to]
    if line:
        where += " AND p.line_id = ?"
        params.append(line)

    sql = f"""
        SELECT p.shift_id, s.shift_name, s.start_time, s.end_time,
               SUM(p.planned_qty) as total_planned,
               SUM(p.actual_qty) as total_actual,
               SUM(p.defect_qty) as total_defects,
               ROUND(SUM(p.actual_qty) * 100.0 / NULLIF(SUM(p.planned_qty), 0), 1) as achievement_rate,
               ROUND(SUM(p.defect_qty) * 100.0 / NULLIF(SUM(p.actual_qty), 0), 2) as defect_rate,
               COUNT(DISTINCT p.production_date) as working_days
        FROM daily_production p
        JOIN shifts s ON p.shift_id = s.shift_id
        {where}
        GROUP BY p.shift_id
        ORDER BY s.start_time
    """
    rows = query(sql, tuple(params))
    return json.dumps(rows, ensure_ascii=False)


@tool
def get_production_trend(
    line: str = "",
    model: str = "",
    days: int = 28,
) -> str:
    """생산 추이 — 일별 생산량과 달성률 트렌드.

    Args:
        line: 라인 ID. 빈 문자열이면 전체.
        model: 모델 ID. 빈 문자열이면 전체.
        days: 최근 N일. 기본값 28(전체 기간).
    """
    where = "WHERE 1=1"
    params = []
    if line:
        where += " AND line_id = ?"
        params.append(line)
    if model:
        where += " AND model_id = ?"
        params.append(model)

    sql = f"""
        SELECT production_date,
               SUM(planned_qty) as planned,
               SUM(actual_qty) as actual,
               SUM(defect_qty) as defects,
               ROUND(SUM(actual_qty) * 100.0 / NULLIF(SUM(planned_qty), 0), 1) as achievement_rate,
               ROUND(SUM(defect_qty) * 100.0 / NULLIF(SUM(actual_qty), 0), 2) as defect_rate
        FROM daily_production
        {where}
        GROUP BY production_date
        ORDER BY production_date DESC
        LIMIT ?
    """
    params.append(days)
    rows = query(sql, tuple(params))
    rows.reverse()
    return json.dumps(rows, ensure_ascii=False)


ALL_TOOLS = [
    get_daily_production,
    get_production_summary,
    get_defect_stats,
    get_line_status,
    get_downtime_history,
    get_model_comparison,
    get_shift_analysis,
    get_production_trend,
]
