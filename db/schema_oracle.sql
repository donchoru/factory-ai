-- Factory AI — Oracle 호환 스키마
-- SQLite schema.sql 기반, Oracle 12c+ 문법으로 변환

-- 생산 라인
CREATE TABLE production_lines (
    line_id        VARCHAR2(20) PRIMARY KEY,
    line_name      VARCHAR2(100) NOT NULL,
    vehicle_type   VARCHAR2(50) NOT NULL,
    capacity_per_shift NUMBER(10) NOT NULL,
    status         VARCHAR2(20) DEFAULT 'ACTIVE'
);

INSERT INTO production_lines VALUES ('LINE-1', '1라인 (세단)', 'SEDAN', 120, 'ACTIVE');
INSERT INTO production_lines VALUES ('LINE-2', '2라인 (SUV)', 'SUV', 80, 'ACTIVE');
INSERT INTO production_lines VALUES ('LINE-3', '3라인 (EV)', 'EV', 60, 'ACTIVE');

-- 차종
CREATE TABLE models (
    model_id       VARCHAR2(20) PRIMARY KEY,
    model_name     VARCHAR2(100) NOT NULL,
    line_id        VARCHAR2(20) NOT NULL REFERENCES production_lines(line_id),
    target_per_shift NUMBER(10) NOT NULL
);

INSERT INTO models VALUES ('SONATA', '소나타', 'LINE-1', 120);
INSERT INTO models VALUES ('TUCSON', '투싼', 'LINE-2', 45);
INSERT INTO models VALUES ('GV70', 'GV70', 'LINE-2', 35);
INSERT INTO models VALUES ('IONIQ6', '아이오닉6', 'LINE-3', 60);

-- 교대
CREATE TABLE shifts (
    shift_id       VARCHAR2(20) PRIMARY KEY,
    shift_name     VARCHAR2(50) NOT NULL,
    start_time     VARCHAR2(10) NOT NULL,
    end_time       VARCHAR2(10) NOT NULL
);

INSERT INTO shifts VALUES ('DAY', '주간', '06:00', '14:00');
INSERT INTO shifts VALUES ('NIGHT', '야간', '14:00', '22:00');
INSERT INTO shifts VALUES ('MIDNIGHT', '심야', '22:00', '06:00');

-- 일별 생산 실적 (핵심 테이블)
CREATE TABLE daily_production (
    id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    production_date   VARCHAR2(10) NOT NULL,
    line_id           VARCHAR2(20) NOT NULL REFERENCES production_lines(line_id),
    model_id          VARCHAR2(20) NOT NULL REFERENCES models(model_id),
    shift_id          VARCHAR2(20) NOT NULL REFERENCES shifts(shift_id),
    planned_qty       NUMBER(10) NOT NULL,
    actual_qty        NUMBER(10) NOT NULL,
    defect_qty        NUMBER(10) DEFAULT 0,
    achievement_rate  NUMBER(5,2),
    note              VARCHAR2(500)
);

CREATE INDEX idx_prod_date ON daily_production(production_date);
CREATE INDEX idx_prod_line ON daily_production(line_id);
CREATE INDEX idx_prod_model ON daily_production(model_id);

-- 불량 상세
CREATE TABLE defects (
    id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    production_date   VARCHAR2(10) NOT NULL,
    line_id           VARCHAR2(20) NOT NULL REFERENCES production_lines(line_id),
    model_id          VARCHAR2(20) NOT NULL REFERENCES models(model_id),
    shift_id          VARCHAR2(20) NOT NULL REFERENCES shifts(shift_id),
    defect_type       VARCHAR2(50) NOT NULL,
    defect_count      NUMBER(10) NOT NULL,
    description       VARCHAR2(500)
);

CREATE INDEX idx_defect_date ON defects(production_date);
CREATE INDEX idx_defect_line ON defects(line_id);

-- 설비 정지 이력
CREATE TABLE downtime (
    id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    line_id           VARCHAR2(20) NOT NULL REFERENCES production_lines(line_id),
    start_datetime    VARCHAR2(20) NOT NULL,
    end_datetime      VARCHAR2(20) NOT NULL,
    duration_minutes  NUMBER(10) NOT NULL,
    reason_type       VARCHAR2(50) NOT NULL,
    description       VARCHAR2(500)
);

CREATE INDEX idx_downtime_line ON downtime(line_id);
