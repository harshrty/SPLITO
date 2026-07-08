# DECISIONS.md — Decision Log & Interview Defense

> How to read this: each decision has **What we chose**, **Options we considered**,
> **Why (in plain words)**, **How we got here**, **Why it will hold up**, and
> **Likely interview questions + answers**. If an evaluator points at a line, the
> reasoning is here.

---

## D1 — Duplicate handling: quarantine and let the human pick

**What we chose:** When two rows look like the same expense, we do NOT auto-delete or
auto-merge. We flag both, hold them in a "quarantine" state, and ask the user to approve
which one to keep.

**Options considered:**
1. Auto-delete the second row (silent).
2. Keep both (do nothing).
3. Quarantine + human approval. ✅

**Why (plain words):** Meera explicitly said "I want to approve anything the app deletes
or changes." A silent delete breaks that promise. Keeping both double-counts money.

**How we got here:** We checked how Splitwise handles it — it surfaces duplicates, it does
not silently merge. Our persona requirement pushed the same way.

**Why it will hold up:** Two detectors, not one. Exact duplicates (Marina Bites: same date,
payer, amount) are caught by hashing core fields. Near-duplicates (Thalassa: same night,
different amount 2400 vs 2450, different payer) are caught by same-date + fuzzy description +
amount-within-tolerance. The hash alone would MISS Thalassa because the amounts differ — that
is exactly why we need the second detector.

**Likely questions:**
- *"Marina Bites and Thalassa are both duplicates — do they hit the same code path?"*
  No. Marina Bites is an exact-hash match. Thalassa is a fuzzy match (amounts differ), a
  separate detector. Both land in quarantine, but through different rules.
- *"Which Thalassa row wins?"* The user picks. The CSV note ("Aisha also logged this, I think
  hers is wrong") is surfaced as a hint but never hardcoded.

---

## D2 — Invalid math (percentages ≠ 100%): hard fail, force a fix

**What we chose:** If a percentage split doesn't total 100% (Pizza Friday = 110%), we reject
the row and require the user to correct it before it can be committed.

**Options considered:**
1. Silently scale the percentages back to 100%.
2. Accept it and let the math be slightly wrong.
3. Hard-fail + require manual correction. ✅

**Why (plain words):** If we silently "fix" 110% we've invented numbers nobody agreed to.
Better to stop and say "these don't add up, fix them."

**How we got here:** No real expense app (Splitwise, Google Pay splits) lets you save a split
that doesn't total the bill. We followed that norm.

**Why it will hold up:** `share` splits are weights and don't need to total anything, so we
only run the 100% check on `percentage` type. We don't over-validate.

**Likely questions:**
- *"Why not just normalize 110% down to 100%?"* Because the group never agreed to those
  adjusted numbers. Silent normalization is the "silent guess" the brief warns against.

---

## D3 — Ambiguous date (May 4 vs Apr 5): always prompt

**What we chose:** For the "Deep cleaning 2026-05-04 (is this April 5 or May 4?)" row, we do
not pick a date automatically. We ask the user.

**Why (plain words):** The date isn't cosmetic — it changes the answer. Sam joined April 8.
If the expense is May 4, Sam is a member and should share it. If it's April 5, Sam wasn't in
yet and shouldn't. A silent default would silently corrupt Sam's balance.

**Why it will hold up:** This ties directly to Sam's requirement ("why would something before
I joined affect me?"). We can demo both dates and show the split membership changing.

**Likely questions:**
- *"Show me what happens if I choose the other date."* The participant set recomputes against
  membership on that date; Sam appears or disappears from the split.

---

## D4 — Currency: date-effective rate table, store original + converted + rate

**What we chose:** We keep every expense's original amount and currency, convert to base INR
using a small rate table keyed by date, and store the rate we used on the expense row.

**Options considered:**
1. Pretend $1 = ₹1 (what the spreadsheet did — wrong, Priya's complaint).
2. Live FX API at import time.
3. Documented date-effective rate table. ✅

**Why (plain words):** Priya said a dollar isn't a rupee. We must convert. But we also must
be able to explain the number later, so we save the rate we used, not just the result.

**How we got here:** Splitwise does NOT use live conversion — it uses a user-set rate and
records it, keeping currencies separate by default. A live API would actually be less faithful
to how the real product behaves, and less reproducible for grading.

**Why it will hold up:** Nothing is destroyed. Original 540 USD stays; converted INR + the
rate + rate source all persist. If asked "what rate did you use on the Goa trip," we point at
the row.

**Likely questions:**
- *"Where does your exchange rate come from?"* A documented `fx_rate` table, effective by date.
  Editable in one row if you want to change it — no code change.
- *"Convert then split, or split then convert?"* Convert to base INR first, then split in
  integer paise. One conversion per expense, no compounding rounding.

---

## D5 — Rounding: deterministic remainder (we deliberately diverge from Splitwise)

**What we chose:** All money math is done in integer paise. When a total doesn't divide evenly,
the leftover paise go to the first *R* participants in a fixed order (ascending person id).
Example: ₹100 / 3 = 3334 + 3333 + 3333 paise.

**Options considered:**
1. Floating point division (banned — precision bugs).
2. Random penny assignment (what Splitwise does).
3. Deterministic integer paise + fixed-order remainder. ✅

**Why (plain words):** Money must add back up to the exact total, every time, and we must be
able to explain who got the extra paisa. Random can't be explained or tested.

**How we got here:** Splitwise assigns the extra penny randomly (they switched to random after
people complained the expense-creator always ate it). We chose NOT to copy that. Random is
un-reproducible and indefensible in a live walkthrough. Deterministic serves Rohan's "no magic
numbers" better.

**Why it will hold up:** Totals reconcile to the paisa by construction. Every split is
reproducible, so it's unit-testable and explainable.

**Likely questions:**
- *"899.995 divided by 4 — walk me through it."* Convert to paise (89999.5 → we reject/҂flag
  sub-paisa input first), then integer-divide, then hand the remainder paise to the first
  participants by id. Totals match exactly.
- *"Splitwise uses random — why don't you?"* Fairness-over-time vs auditability. For a group
  that needs to trust and verify every number, deterministic and explainable beats statistically
  fair but random.

---

## D6 — Backend stack: Django + DRF (recommended) — CONFIRM

**What we chose (pending your confirmation):** Django REST Framework.

**Options considered:**
1. Django + DRF. ✅ (recommended)
2. FastAPI + SQLAlchemy.

**Why (plain words):** It's a 2-day build. Django ships with auth, admin, migrations, and
serializers, so we spend time on the anomaly logic (the graded part), not on plumbing. It also
matches the JD, which literally says "Write Django REST APIs."

**Why it will hold up:** The Django admin gives us a free UI to inspect the quarantine/anomaly
tables during the live demo.

**Note:** FastAPI is a fine choice if you're faster in it — just own the reason here.

---

## D7 — Guests are people but not members (Dev, Kabir)

**What we chose:** A `person` can participate in a split without being a `member`. Dev (trip)
and Kabir (one day) are guests.

**Why (plain words):** They spent money together on the trip but never lived in the flat. If we
forced everyone in a split to be a member, every Goa row would false-flag as an error.

**Why it will hold up:** Temporal membership checks (D3/Sam) only apply to members. Guests are
allowed on any split they appear in, no date check.

**Likely questions:**
- *"Is Kabir on the parasailing a data error?"* No — he's a legitimate one-day guest. Our
  temporal validator skips guests, so it doesn't false-flag him.

---

## D8 — Balances are derived, never stored

**What we chose:** We never store a "balance" column. We compute it on read from paid, owed,
and settlements.

**Why (plain words):** A stored balance drifts the moment any expense changes. Recomputing from
the ledger is cheap at this scale and always correct.

**Why it will hold up:** Rohan gets his itemized audit for free — his balance IS the list of
his split rows. Aisha's "one number" is the same data, simplified.

---

## D9 — Settlements are their own entity, not expenses

**What we chose:** "Rohan paid Aisha back" and "Sam deposit share" are money transfers, not
shared costs. They go in a `settlement` table.

**Why (plain words):** A payment cancels debt; it isn't a new shared cost. Logging it as an
expense double-counts and flips balances the wrong way.

**Why it will hold up:** The "Sam deposit" row even has `split_type=equal`, so a naive
"missing split_type ⇒ settlement" rule would MISS it. We detect it by shape (single
counterparty + payment semantics) and route it to quarantine for reclassification — not silently.

**Likely questions:**
- *"Rohan paid Aisha back is logged as an expense — trace it."* Detector flags it as a probable
  settlement → quarantine → on approval it's written to the settlement table (Rohan → Aisha),
  not the expense ledger.

---

## Cross-cutting principle

Every anomaly follows the same spine: **detect → surface → quarantine → human approves →
commit**. Nothing is silently guessed and nothing is silently dropped. That single sentence
answers most "why did you do X" questions.
