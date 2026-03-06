-- Factory AI — 자동차 공장 생산 데이터 스키마

PRAGMA foreign_keys = ON;

-- 생산 라인
CREATE TABLE IF NOT EXISTS production_lines (
    line_id     TEXT PRIMARY KEY,
    line_name   TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    capacity_per_shift INTEGER NOT NULL,
    status      TEXT DEFAULT 'ACTIVE'
);

INSERT INTO production_lines VALUES ('LINE-1', '1라인 (세단)', 'SEDAN', 120, 'ACTIVE');
INSERT INTO production_lines VALUES ('LINE-2', '2라인 (SUV)', 'SUV', 80, 'ACTIVE');
INSERT INTO production_lines VALUES ('LINE-3', '3라인 (EV)', 'EV', 60, 'ACTIVE');

-- 차종
CREATE TABLE IF NOT EXISTS models (
    model_id    TEXT PRIMARY KEY,
    model_name  TEXT NOT NULL,
    line_id     TEXT NOT NULL REFERENCES production_lines(line_id),
    target_per_shift INTEGER NOT NULL
);

INSERT INTO models VALUES ('SONATA', '소나타', 'LINE-1', 120);
INSERT INTO models VALUES ('TUCSON', '투싼', 'LINE-2', 45);
INSERT INTO models VALUES ('GV70', 'GV70', 'LINE-2', 35);
INSERT INTO models VALUES ('IONIQ6', '아이오닉6', 'LINE-3', 60);

-- 교대
CREATE TABLE IF NOT EXISTS shifts (
    shift_id    TEXT PRIMARY KEY,
    shift_name  TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL
);

INSERT INTO shifts VALUES ('DAY', '주간', '06:00', '14:00');
INSERT INTO shifts VALUES ('NIGHT', '야간', '14:00', '22:00');
INSERT INTO shifts VALUES ('MIDNIGHT', '심야', '22:00', '06:00');

-- 일별 생산 실적 (핵심 테이블)
CREATE TABLE IF NOT EXISTS daily_production (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    production_date TEXT NOT NULL,
    line_id         TEXT NOT NULL REFERENCES production_lines(line_id),
    model_id        TEXT NOT NULL REFERENCES models(model_id),
    shift_id        TEXT NOT NULL REFERENCES shifts(shift_id),
    planned_qty     INTEGER NOT NULL,
    actual_qty      INTEGER NOT NULL,
    defect_qty      INTEGER DEFAULT 0,
    achievement_rate REAL,
    note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_prod_date ON daily_production(production_date);
CREATE INDEX IF NOT EXISTS idx_prod_line ON daily_production(line_id);
CREATE INDEX IF NOT EXISTS idx_prod_model ON daily_production(model_id);

-- 불량 상세
CREATE TABLE IF NOT EXISTS defects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    production_date TEXT NOT NULL,
    line_id         TEXT NOT NULL REFERENCES production_lines(line_id),
    model_id        TEXT NOT NULL REFERENCES models(model_id),
    shift_id        TEXT NOT NULL REFERENCES shifts(shift_id),
    defect_type     TEXT NOT NULL,
    defect_count    INTEGER NOT NULL,
    description     TEXT
);

CREATE INDEX IF NOT EXISTS idx_defect_date ON defects(production_date);
CREATE INDEX IF NOT EXISTS idx_defect_line ON defects(line_id);

-- 설비 정지 이력
CREATE TABLE IF NOT EXISTS downtime (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id           TEXT NOT NULL REFERENCES production_lines(line_id),
    start_datetime    TEXT NOT NULL,
    end_datetime      TEXT NOT NULL,
    duration_minutes  INTEGER NOT NULL,
    reason_type       TEXT NOT NULL,
    description       TEXT
);

CREATE INDEX IF NOT EXISTS idx_downtime_line ON downtime(line_id);
