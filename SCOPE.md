# SCOPE.md — Data Model, Database Schema & Anomaly Log

> Deliverable per assignment: (1) database schema, (2) anomaly log (every data problem in the
> CSV and how it's handled). Validation limits from the design phase are baked into the DDL
> constraints below.

---

## Part 1 — Data model (logical)

Three layers. Identity/membership define *who*; the ledger is the source of truth for *money*;
the import layer is a quarantine that never lets bad data reach the ledger without approval.

```
IDENTITY & MEMBERSHIP        LEDGER (source of truth)        IMPORT & QUARANTINE
─────────────────────        ────────────────────────        ───────────────────
app_user                     expense ──< expense_share       import_batch ──< staged_row
expense_group ──< person     settlement                      staged_row  ──< anomaly
person ──< person_alias      fx_rate
expense_group ──< membership
```

### Entity catalog (12 tables + 1 view)

| # | Entity | Purpose | Key design note |
|---|---|---|---|
| 1 | `app_user` | Login accounts | Separate from `person` — a balance can exist without a login (Meera) |
| 2 | `expense_group` | A shared-expense group | Holds `base_currency` (INR); everything converts to it |
| 3 | `person` | A balance-bearing participant | `is_guest` flag (Dev, Kabir) — guests skip temporal checks |
| 4 | `person_alias` | Name normalization | Maps `priya`/`Priya S`/`rohan ` → one `person` |
| 5 | `membership` | Time-bounded stay | `joined_on`/`left_on` answer "member on date D?" (Sam, Meera) |
| 6 | `fx_rate` | Currency conversion | Date-effective rates; edit a row, not code |
| 7 | `expense` | A shared cost | Stores original + base amount + rate; `status` keeps voided dups |
| 8 | `expense_share` | One split line per participant | Rohan's itemized audit; sums exactly to expense base amount |
| 9 | `settlement` | A payment/transfer | NOT an expense — avoids double-counting |
| 10 | `import_batch` | One CSV upload | Provenance for every imported row |
| 11 | `staged_row` | Raw CSV, untouched | Tolerant ingest — never crashes on bad data |
| 12 | `anomaly` | One detected problem + fix | The Import Report is a SELECT over this table |
| V | `person_balance` (view) | Derived net balance | Balances are computed, never stored (D8) |

---

## Part 2 — Physical schema (PostgreSQL DDL)

> Conventions: money is **integer minor units** (paise) in `BIGINT` — never float (D5).
> Enums are `CHECK IN (...)` on short `VARCHAR` (easy to read, easy to extend, ORM-friendly).
> Identity columns use `GENERATED ALWAYS AS IDENTITY`. Field lengths match the validation spec.

```sql
-- ============================================================
-- LAYER A — IDENTITY & MEMBERSHIP
-- ============================================================

CREATE TABLE app_user (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         VARCHAR(254) NOT NULL UNIQUE
                    CHECK (char_length(email) >= 5 AND email = lower(email)),
    password_hash VARCHAR(255) NOT NULL,          -- hash only, raw password never stored
    display_name  VARCHAR(80)  NOT NULL
                    CHECK (char_length(btrim(display_name)) >= 1),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE expense_group (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR(100) NOT NULL CHECK (char_length(btrim(name)) >= 1),
    base_currency CHAR(3)      NOT NULL DEFAULT 'INR'
                    CHECK (base_currency IN ('INR','USD')),
    created_by    BIGINT       REFERENCES app_user(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE person (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id       BIGINT      NOT NULL REFERENCES expense_group(id) ON DELETE CASCADE,
    canonical_name VARCHAR(80) NOT NULL CHECK (char_length(btrim(canonical_name)) >= 1),
    is_guest       BOOLEAN     NOT NULL DEFAULT FALSE,
    user_id        BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (group_id, canonical_name)             -- one 'Rohan' per group
);

CREATE TABLE person_alias (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id   BIGINT       NOT NULL REFERENCES expense_group(id) ON DELETE CASCADE,
    person_id  BIGINT       NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    raw_alias  VARCHAR(120) NOT NULL                 -- stored verbatim (may hold trailing space)
);
-- an alias resolves to exactly one person within a group (case/space-insensitive)
CREATE UNIQUE INDEX ux_alias_norm
    ON person_alias (group_id, lower(btrim(raw_alias)));

CREATE TABLE membership (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id  BIGINT NOT NULL REFERENCES expense_group(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    joined_on DATE   NOT NULL,
    left_on   DATE,                                  -- NULL = still active
    CHECK (left_on IS NULL OR left_on > joined_on)
);
CREATE INDEX ix_membership_lookup ON membership (group_id, person_id);

-- ============================================================
-- LAYER B — LEDGER
-- ============================================================

CREATE TABLE fx_rate (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    currency       CHAR(3)       NOT NULL CHECK (currency IN ('INR','USD')),
    rate_to_base   NUMERIC(12,6) NOT NULL CHECK (rate_to_base > 0),
    effective_date DATE          NOT NULL,
    UNIQUE (currency, effective_date)
);

CREATE TABLE expense (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id              BIGINT       NOT NULL REFERENCES expense_group(id) ON DELETE CASCADE,
    spent_on              DATE         NOT NULL,
    description           VARCHAR(200) NOT NULL CHECK (char_length(btrim(description)) >= 1),
    paid_by_person_id     BIGINT       REFERENCES person(id) ON DELETE RESTRICT,  -- NULL = missing-payer quarantine
    original_amount_minor BIGINT       NOT NULL                                    -- may be negative (refund)
                            CHECK (original_amount_minor BETWEEN -1000000000 AND 10000000000),
    original_currency     CHAR(3)      NOT NULL CHECK (original_currency IN ('INR','USD')),
    amount_base_minor     BIGINT       NOT NULL,
    fx_rate               NUMERIC(12,6) NOT NULL DEFAULT 1 CHECK (fx_rate > 0),
    fx_rate_source        VARCHAR(100),
    split_type            VARCHAR(12)  NOT NULL
                            CHECK (split_type IN ('equal','unequal','percentage','share')),
    status                VARCHAR(8)   NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','void')),
    notes                 VARCHAR(500),
    import_batch_id       BIGINT       REFERENCES import_batch(id) ON DELETE SET NULL,
    source_row_number     INTEGER,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_expense_group_date ON expense (group_id, spent_on);
CREATE INDEX ix_expense_payer      ON expense (paid_by_person_id);

CREATE TABLE expense_share (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expense_id          BIGINT        NOT NULL REFERENCES expense(id) ON DELETE CASCADE,
    person_id           BIGINT        NOT NULL REFERENCES person(id) ON DELETE RESTRICT,
    share_input         NUMERIC(12,2) NOT NULL CHECK (share_input >= 0),  -- 700 | 30(%) | 2(shares)
    computed_owed_minor BIGINT        NOT NULL,                            -- server-computed only
    UNIQUE (expense_id, person_id)
);
CREATE INDEX ix_share_person ON expense_share (person_id);

CREATE TABLE settlement (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id       BIGINT      NOT NULL REFERENCES expense_group(id) ON DELETE CASCADE,
    from_person_id BIGINT      NOT NULL REFERENCES person(id) ON DELETE RESTRICT,
    to_person_id   BIGINT      NOT NULL REFERENCES person(id) ON DELETE RESTRICT,
    amount_minor   BIGINT      NOT NULL CHECK (amount_minor > 0),  -- stored in group base currency (INR)
    currency       CHAR(3)     NOT NULL DEFAULT 'INR' CHECK (currency IN ('INR','USD')),
    settled_on     DATE        NOT NULL,
    note           VARCHAR(300),
    origin         VARCHAR(24) NOT NULL DEFAULT 'manual'
                     CHECK (origin IN ('manual','reclassified_from_import')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (from_person_id <> to_person_id)          -- no self-settlement
);
CREATE INDEX ix_settlement_group ON settlement (group_id);

-- ============================================================
-- LAYER C — IMPORT & QUARANTINE
-- ============================================================

CREATE TABLE import_batch (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id    BIGINT       NOT NULL REFERENCES expense_group(id) ON DELETE CASCADE,
    filename    VARCHAR(255) NOT NULL,
    status      VARCHAR(12)  NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','committed')),
    uploaded_by BIGINT       REFERENCES app_user(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE staged_row (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id   BIGINT  NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_json   JSONB   NOT NULL                     -- every original cell, unvalidated
);
CREATE INDEX ix_staged_batch ON staged_row (batch_id);

CREATE TABLE anomaly (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id            BIGINT       NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    staged_row_id       BIGINT       REFERENCES staged_row(id) ON DELETE CASCADE,
    anomaly_type        VARCHAR(32)  NOT NULL CHECK (anomaly_type IN (
                            'exact_dup','fuzzy_dup','pct_not_100','unequal_sum_mismatch',
                            'ambiguous_date','out_of_bounds_date','missing_payer','missing_currency',
                            'negative_amount','zero_amount','sub_unit_amount','type_detail_conflict',
                            'non_member','ex_member','settlement_as_expense','name_alias')),
    severity            VARCHAR(8)   NOT NULL CHECK (severity IN ('block','warn')),
    detail              VARCHAR(300) NOT NULL,        -- human sentence for the Import Report
    proposed_action     VARCHAR(32)  NOT NULL CHECK (proposed_action IN (
                            'void_dup','merge','reclassify_settlement','normalize_name',
                            'convert_currency','exclude_person','request_input','reject','skip')),
    status              VARCHAR(12)  NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','approved','rejected','edited')),
    resolved_value_json JSONB,
    reviewed_by         BIGINT       REFERENCES app_user(id) ON DELETE SET NULL,
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_anomaly_batch  ON anomaly (batch_id);
CREATE INDEX ix_anomaly_status ON anomaly (status);

-- ============================================================
-- DERIVED BALANCE (D8: balances are computed, never stored)
-- net_minor > 0  => person is owed money (others owe them)
-- net_minor < 0  => person owes money
-- ============================================================

CREATE VIEW person_balance AS
SELECT p.id                                       AS person_id,
       p.group_id,
       COALESCE(paid.total, 0)
       - COALESCE(owed.total, 0)
       - COALESCE(sent.total, 0)
       + COALESCE(recv.total, 0)                  AS net_minor
FROM person p
LEFT JOIN (
    SELECT paid_by_person_id, SUM(amount_base_minor) AS total
    FROM expense WHERE status = 'active'
    GROUP BY paid_by_person_id
) paid ON paid.paid_by_person_id = p.id
LEFT JOIN (
    SELECT es.person_id, SUM(es.computed_owed_minor) AS total
    FROM expense_share es
    JOIN expense e ON e.id = es.expense_id
    WHERE e.status = 'active'
    GROUP BY es.person_id
) owed ON owed.person_id = p.id
LEFT JOIN (
    SELECT from_person_id, SUM(amount_minor) AS total
    FROM settlement GROUP BY from_person_id
) sent ON sent.from_person_id = p.id
LEFT JOIN (
    SELECT to_person_id, SUM(amount_minor) AS total
    FROM settlement GROUP BY to_person_id
) recv ON recv.to_person_id = p.id;
```

### Schema notes / defensible choices
- **`ON DELETE RESTRICT` on person↔expense/share/settlement:** you cannot delete a person who
  has financial history — protects balance integrity. `CASCADE` only where a child is meaningless
  without its parent (aliases, shares, staged rows, anomalies).
- **`settlement.amount_minor` is in base currency (INR):** simplification for MVP — settle-ups
  happen in the home currency. Documented as a deliberate scope decision (DECISIONS.md candidate).
- **`person_balance` is a VIEW, not a table:** recomputes from the ledger every read, so it can
  never drift. At this data size the aggregation is trivially cheap.
- **The Import Report** = `SELECT anomaly_type, detail, proposed_action, status FROM anomaly
  WHERE batch_id = ? ORDER BY severity, staged_row_id`.

---

## Part 3 — Anomaly log (every problem found in expenses_export.csv)

17 distinct problems detected (assignment promises "at least 12"). Each: how we **detect**,
how we **surface**, and the **policy**. Severity `block` = cannot commit until resolved;
`warn` = committed with a flag.

| # | CSV row(s) | anomaly_type | Detection rule | Policy (proposed_action) | Sev |
|---|---|---|---|---|---|
| 1 | Marina Bites ×2 (Feb 8) | `exact_dup` | hash(date,payer,amount,norm-desc) collision | quarantine → user keeps one → `void_dup` | block |
| 2 | Thalassa 2400 vs 2450 (Mar 11) | `fuzzy_dup` | same date + fuzzy desc + amount within tolerance | quarantine → user picks winner → `void_dup`/`merge` | block |
| 3 | `priya`,`Priya S`,`rohan ` | `name_alias` | normalized name ∉ known aliases | `normalize_name` via alias table (auto, logged) | warn |
| 4 | House cleaning (Feb 22) | `missing_payer` | `paid_by` empty | suspend row → `request_input` | block |
| 5 | "Rohan paid Aisha back" (Feb 25) | `settlement_as_expense` | empty split_type + 1 counterparty + payment note | `reclassify_settlement` (Rohan→Aisha) | block |
| 6 | "Sam deposit share" (Apr 8) | `settlement_as_expense` | payer≠beneficiary, single participant, deposit note | `reclassify_settlement` (Sam→Aisha) — note: has split_type=equal, so detect by *shape* | block |
| 7 | Pizza 110%, Weekend brunch 110% | `pct_not_100` | Σ percentages ≠ 100 | `reject` → require correction to 100% | block |
| 8 | Goa villa/lunch/parasailing (USD) | `convert_currency` | currency = USD | `convert_currency` via fx_rate, store original+base+rate | warn |
| 9 | Groceries DMart (Mar 15) | `missing_currency` | currency blank | default INR + flag in report | warn |
| 10 | Parasailing refund −30 USD (Mar 12) | `negative_amount` | amount < 0 | treat as refund (signed expense) → `skip` special-case OR keep, user confirms | warn |
| 11 | Airport cab 2014-03-01 | `out_of_bounds_date` | date < group_min or > today | `reject`/correct with approval | block |
| 12 | Deep cleaning 2026-05-04 | `ambiguous_date` | note flags ambiguity / impossible-day heuristic | `request_input` — user disambiguates (changes if Sam is in split) | block |
| 13 | Swiggy order = 0 (Mar 22) | `zero_amount` | amount = 0 | `skip` (no economic effect), logged | warn |
| 14 | Cylinder refill 899.995 | `sub_unit_amount` | > 2 decimal places | round HALF_UP to paise, flag; deterministic remainder | warn |
| 15 | Furniture (Apr 18) | `type_detail_conflict` | split_type=equal AND split_details present | honor `equal`, ignore stray shares, flag | warn |
| 16 | Parasailing incl. Kabir (Mar 11) | `non_member` | participant ∉ members AND ∉ known guests | add as guest `person` (is_guest=true), include in split | warn |
| 17 | Groceries BigBasket (Apr 2) incl. Meera | `ex_member` | participant not a member on spent_on (Meera left Mar 31) | `exclude_person`, redistribute, flag (Sam's concern) | block |

> Not anomalies (documented so we don't "fix" them): Movie night excludes Meera (**legit** partial
> split); April rent share Aisha 2/Rohan 1/Priya 1 (**legit** — Aisha took Meera's room).
