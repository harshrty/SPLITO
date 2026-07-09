# AI_USAGE.md

## Tools used

- **Claude (Anthropic)** — primary development collaborator for design, code, and tests.
- Used as a pair: I (engineer of record) drove the sequence, made every product/engineering
  decision, reviewed all output, and verified behaviour. Claude wrote code and docs to my
  direction and caught/fixed issues on request.

## How I worked with it

I deliberately went **design-first** before any code: requirements → decisions → schema →
data-flow → HLD → LLD, then implemented in small, tested, individually-committed steps. This is
visible in the commit history (docs commits precede the `feat(...)` commits).

### Key prompts (paraphrased)

- "Act as PM + developer; here's the assignment and CSV — architect it, no code yet."
- "For each open decision, what do Splitwise / real apps do? Find papers and recommend."
- "Strong validation and field limits for everything."
- "Now verify the data model in depth." / "Verify everything in depth."
- "Did you do an end-to-end test?"
- "Build step by step; I review every line."

The verification prompts mattered most — they're where the AI's mistakes below were caught.

## Three concrete cases where the AI was wrong, how I caught it, what changed

### 1. Balance view had the settlement signs backwards (correctness bug)

**What the AI produced:** the `person_balance` view computed
`net = paid − owed − sent + received`.

**How I caught it:** I asked it to verify the data model and hand-traced a settlement:
Aisha paid ₹48,000 rent (₹12,000 each), then Rohan pays Aisha ₹5,000. Rohan should then owe
₹7,000 — but the formula gave **−₹17,000**. The nasty part: the group still summed to zero, so a
naive "does it balance?" check would have passed while every individual number was wrong.

**What changed:** flipped to `net = paid − owed + sent − received` (money you *send* pays down your
debt). Added `test_settlement_signs_are_correct` as a regression test.
_Commit: `fix(schema): correct settlement signs in balance view` (`eb675b8`)._

### 2. DDL referenced a table before it was created (would not run)

**What the AI produced:** in the SCOPE.md schema, `CREATE TABLE expense` had a foreign key to
`import_batch`, but `import_batch` was created **later** in the same script.

**How I caught it:** reasoning about execution order — Postgres runs DDL top-to-bottom, so the
forward reference errors out. Caught while reviewing the schema, before it ever ran.

**What changed:** dropped the inline FK and added it via `ALTER TABLE ... ADD CONSTRAINT` after both
tables exist. The Django models later confirmed this ordering.
_Commit: `fix(schema): resolve expense→import_batch forward reference via ALTER` (`b1bcfa4`)._

### 3. `expense_share.share_input` was NOT NULL but equal splits have no input

**What the AI produced:** `share_input NUMERIC(12,2) NOT NULL`.

**How I caught it:** during schema verification I worked through how each split type stores its
per-person input. An **equal** split has no per-person input value — there was nothing valid to put
in a NOT NULL column, so the constraint was impossible to satisfy honestly.

**What changed:** made it nullable (`NULL` for equal; populated for unequal/percentage/share), and
the SplitEngine returns `share_input=None` for equal splits.
_Commit: same verification pass (`eb675b8`); enforced in `apps/expenses/services/split_engine.py`._

### (Bonus, caught this session) report generator collided with seeded data

The first `generate_import_report` used `FxRate.objects.create(...)`, which threw an
`IntegrityError` because the dev DB already had that rate seeded. Caught on first run; changed to
`get_or_create`.

## What I take responsibility for

Every line here is mine to explain. The AI accelerated writing and caught its own errors when I
pushed it to verify — but the decisions (rounding rule, FX basis, deterministic-over-random,
Person≠User, quarantine-before-ledger) and the catches above came from actively reviewing and
hand-checking its output, not from accepting it.
