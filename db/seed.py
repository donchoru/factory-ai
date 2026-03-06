"""가상 생산 데이터 생성 — 2026-02-01 ~ 2026-02-28."""
import random
import sqlite3
from datetime import date, timedelta, datetime
from pathlib import Path

random.seed(42)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "factory.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# ── 기본 설정 ────────────────────────────────────────────
START_DATE = date(2026, 2, 1)
END_DATE = date(2026, 2, 28)

# 라인별 모델 매핑
LINE_MODELS = {
    "LINE-1": ["SONATA"],
    "LINE-2": ["TUCSON", "GV70"],
    "LINE-3": ["IONIQ6"],
}

# 모델별 교대당 계획 수량
MODEL_TARGET = {
    "SONATA": 120,
    "TUCSON": 45,
    "GV70": 35,
    "IONIQ6": 60,
}

SHIFTS = ["DAY", "NIGHT", "MIDNIGHT"]

DEFECT_TYPES = ["paint", "assembly", "welding", "electric"]
DEFECT_DESC = {
    "paint": ["도장 흐름", "색상 불균일", "스크래치", "오렌지필"],
    "assembly": ["볼트 토크 미달", "패널 갭 초과", "배선 미체결", "시트 장착 불량"],
    "welding": ["용접 기공", "스패터 과다", "용접 비드 불량", "용접 강도 미달"],
    "electric": ["센서 오류", "배터리 셀 불량", "모터 진동 초과", "BMS 통신 에러"],
}

DOWNTIME_PLANNED = [
    ("LINE-1", "2026-02-08", "06:00", "10:00", 240, "계획정비: 도장 부스 필터 교체"),
    ("LINE-2", "2026-02-08", "06:00", "14:00", 480, "계획정비: 용접 로봇 캘리브레이션"),
    ("LINE-3", "2026-02-01", "06:00", "14:00", 480, "계획정비: EV 배터리 라인 점검"),
    ("LINE-3", "2026-02-15", "06:00", "14:00", 480, "계획정비: 모터 조립 설비 점검"),
    ("LINE-1", "2026-02-22", "06:00", "08:00", 120, "계획정비: 컨베이어 벨트 점검"),
    ("LINE-3", "2026-02-22", "06:00", "14:00", 480, "계획정비: 배터리 모듈 라인 정비"),
]

DOWNTIME_UNPLANNED_REASONS = [
    ("equipment_failure", ["로봇 암 과열 정지", "컨베이어 모터 고장", "PLC 통신 장애", "유압 라인 누유"]),
    ("material_shortage", ["도어 패널 입고 지연", "반도체 칩 부족", "배터리 셀 공급 지연", "시트 프레임 미입고"]),
    ("quality_issue", ["도장 품질 이슈 라인 정지", "용접 강도 재검사", "배터리 셀 전수검사"]),
]


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun


def _is_sunday(d: date) -> bool:
    return d.weekday() == 6


def _generate_production(conn: sqlite3.Connection):
    """일별 생산 실적 생성."""
    rows = []
    current = START_DATE
    while current <= END_DATE:
        for line_id, model_ids in LINE_MODELS.items():
            # 일요일: LINE-3 계획정비로 미가동
            if _is_sunday(current) and line_id == "LINE-3":
                continue

            for model_id in model_ids:
                target = MODEL_TARGET[model_id]

                for shift in SHIFTS:
                    # 심야 교대: 일요일 미가동, 토요일 감산
                    if _is_sunday(current) and shift == "MIDNIGHT":
                        continue
                    if _is_weekend(current) and shift == "MIDNIGHT" and line_id != "LINE-1":
                        continue

                    planned = target

                    # 달성률 결정
                    if _is_sunday(current):
                        rate = random.uniform(0.70, 0.82)
                    elif _is_weekend(current):
                        rate = random.uniform(0.75, 0.88)
                    else:
                        rate = random.uniform(0.90, 1.00)

                    # EV 라인은 약간 변동 큼
                    if line_id == "LINE-3":
                        rate *= random.uniform(0.95, 1.02)
                        rate = min(rate, 1.0)

                    actual = max(0, round(planned * rate))
                    achievement = round(actual / planned * 100, 1) if planned > 0 else 0

                    # 불량 수
                    if line_id == "LINE-3":
                        defect_rate = random.uniform(0.02, 0.04)
                    elif line_id == "LINE-2":
                        defect_rate = random.uniform(0.005, 0.02)
                    else:
                        defect_rate = random.uniform(0.005, 0.015)
                    defect_qty = max(0, round(actual * defect_rate))

                    note = None
                    if achievement < 80:
                        note = "달성률 부진"
                    elif defect_qty > actual * 0.03:
                        note = "불량률 주의"

                    rows.append((
                        current.isoformat(), line_id, model_id, shift,
                        planned, actual, defect_qty, achievement, note,
                    ))

        current += timedelta(days=1)

    conn.executemany(
        "INSERT INTO daily_production (production_date, line_id, model_id, shift_id, "
        "planned_qty, actual_qty, defect_qty, achievement_rate, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    print(f"  daily_production: {len(rows)}행")
    return rows


def _generate_defects(conn: sqlite3.Connection, production_rows: list):
    """불량 상세 생성 — 생산 실적 기반."""
    defect_rows = []
    for prod_date, line_id, model_id, shift_id, _, _, defect_qty, _, _ in production_rows:
        if defect_qty == 0:
            continue

        # 불량 유형별 분배
        remaining = defect_qty
        types = random.sample(DEFECT_TYPES, k=min(len(DEFECT_TYPES), random.randint(1, 3)))
        for i, dtype in enumerate(types):
            if i == len(types) - 1:
                count = remaining
            else:
                count = random.randint(1, max(1, remaining - (len(types) - i - 1)))
                remaining -= count

            if count <= 0:
                continue

            desc = random.choice(DEFECT_DESC[dtype])
            defect_rows.append((prod_date, line_id, model_id, shift_id, dtype, count, desc))

    conn.executemany(
        "INSERT INTO defects (production_date, line_id, model_id, shift_id, "
        "defect_type, defect_count, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
        defect_rows,
    )
    print(f"  defects: {len(defect_rows)}행")


def _generate_downtime(conn: sqlite3.Connection):
    """설비 정지 이력 생성."""
    rows = []

    # 계획 정비
    for line_id, dt, start, end, duration, desc in DOWNTIME_PLANNED:
        rows.append((
            line_id,
            f"{dt}T{start}",
            f"{dt}T{end}",
            duration,
            "planned_maintenance",
            desc,
        ))

    # 비계획 정지 (랜덤)
    for _ in range(12):
        line_id = random.choice(["LINE-1", "LINE-2", "LINE-3"])
        day_offset = random.randint(0, 27)
        d = START_DATE + timedelta(days=day_offset)
        if _is_sunday(d):
            continue

        hour = random.randint(6, 20)
        duration = random.choice([30, 45, 60, 90, 120, 180])
        start_dt = datetime(d.year, d.month, d.day, hour, 0)
        end_dt = start_dt + timedelta(minutes=duration)

        reason_type, descs = random.choice(DOWNTIME_UNPLANNED_REASONS)
        desc = random.choice(descs)

        rows.append((
            line_id,
            start_dt.strftime("%Y-%m-%dT%H:%M"),
            end_dt.strftime("%Y-%m-%dT%H:%M"),
            duration,
            reason_type,
            desc,
        ))

    conn.executemany(
        "INSERT INTO downtime (line_id, start_datetime, end_datetime, "
        "duration_minutes, reason_type, description) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    print(f"  downtime: {len(rows)}행")


def seed():
    """DB 초기화 + 시드 데이터 생성."""
    # 기존 DB 삭제
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"기존 DB 삭제: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    # 스키마 실행
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    print("스키마 생성 완료")

    # 데이터 생성
    print("데이터 생성 중...")
    production_rows = _generate_production(conn)
    _generate_defects(conn, production_rows)
    _generate_downtime(conn)

    conn.commit()

    # 검증
    print("\n검증:")
    for table in ["production_lines", "models", "shifts", "daily_production", "defects", "downtime"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}행")

    conn.close()
    print(f"\nDB 생성 완료: {DB_PATH}")


if __name__ == "__main__":
    seed()
