# ARCHITECTURE.md

## 1. Overview

`loan-calc` is a small Python command-line application for retail loan
calculations (EMI, amortisation schedules, prepayment savings, offer
comparison, and loan eligibility). The project is organised into two parts:

- **`loan_calc/` package** — contains all the calculation logic
  (`calculator.py`), re-exported through `__init__.py`.
- **`cli.py`** — a thin command-line interface built with `argparse` that
  parses user input, calls into `loan_calc`, and prints the results as
  JSON (or plain dict rows for the amortisation schedule).

```
cli.py
  └── loan_calc (package)
        ├── __init__.py          -> from .calculator import *
        └── calculator.py        -> all business logic / pure functions
```

There is no persistent state, database, or network I/O. Most functions in
`calculator.py` are pure (deterministic, given the same inputs they return
the same outputs), with two exceptions: `schedule_to_csv`, which performs
file I/O, and `summary`, which is impure when called without an explicit
`start` argument — in that case it defaults to `date.today()`, so its
`last_emi` output (and therefore the whole returned dict) can differ
depending on the date the function is called, even with identical
`principal`/`annual_rate`/`tenure_months` inputs.

## 2. Modules

### 2.1 `loan_calc/__init__.py`

Re-exports everything from `calculator.py` via `from .calculator import *`,
so consumers can `import loan_calc` and access functions such as
`loan_calc.emi(...)` directly, or `from loan_calc import emi`.

### 2.2 `loan_calc/calculator.py`

Contains a module-level constant and all calculation functions.

- `DEFAULT_CURRENCY = "INR"` — the currency code used in `summary()`'s
  output.

### 2.3 `cli.py`

The command-line entry point. Imports `amortisation_schedule`,
`prepayment_savings`, and `summary` from `loan_calc`, defines `main()`,
and invokes it when the script is run directly.

## 3. Function reference

Each function below is documented with its purpose, parameters, return
value, and any functions it calls or is called by.

---

### `_monthly_rate(annual_rate)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Converts an annual interest rate (percentage) into a
  monthly decimal rate, rounded to 4 decimal places.
- **Parameters:**
  - `annual_rate` (number) — annual interest rate expressed as a
    percentage (e.g. `9` for 9%).
- **Returns:** `float` — the monthly rate, computed as
  `round(annual_rate / 1200, 4)`.
- **Called by:** `emi()`, `amortisation_schedule()`, `eligible_amount()`.
- **Calls:** none (built-in `round` only).

---

### `emi(principal, annual_rate, tenure_months)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Calculates the Equated Monthly Instalment (EMI) for a loan
  using the standard amortising-loan formula.
- **Parameters:**
  - `principal` (number) — loan principal amount; must be > 0.
  - `annual_rate` (number) — annual interest rate as a percentage.
  - `tenure_months` (int) — loan tenure in months; must be > 0.
- **Returns:** `float` — the EMI amount, rounded to 2 decimal places.
  - If `tenure_months <= 0`, raises `ValueError("tenure must be positive")`.
  - If `principal <= 0`, raises `ValueError("principal must be positive")`.
  - If the monthly rate is `0` (zero-interest loan), returns
    `principal / tenure_months`.
  - Otherwise uses the formula `P * r * (1+r)^n / ((1+r)^n - 1)`.
- **Calls:** `_monthly_rate()`.
- **Called by:** `total_payment()`, `amortisation_schedule()`,
  `prepayment_savings()`, `compare_offers()`, `summary()`.

---

### `total_payment(principal, annual_rate, tenure_months)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Calculates the total amount repaid over the full loan
  tenure (EMI × number of instalments).
- **Parameters:** same as `emi()`.
- **Returns:** `float` — `emi(...) * tenure_months`, rounded to 2 decimals.
- **Calls:** `emi()`.
- **Called by:** `total_interest()`, `summary()`.

---

### `total_interest(principal, annual_rate, tenure_months)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Calculates the total interest paid over the loan tenure.
- **Parameters:** same as `emi()`.
- **Returns:** `float` — `total_payment(...) - principal`, rounded to 2
  decimals.
- **Calls:** `total_payment()`.
- **Called by:** `prepayment_savings()`, `compare_offers()`, `summary()`.

---

### `amortisation_schedule(principal, annual_rate, tenure_months)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Builds the month-by-month amortisation schedule, showing
  how each EMI splits into interest and principal, and the outstanding
  balance after each payment.
- **Parameters:** same as `emi()`.
- **Returns:** `list[dict]` — one dict per month with keys:
  - `month` — month number (1-indexed).
  - `emi` — instalment amount for that month.
  - `interest` — interest portion of that month's instalment.
  - `principal` — principal portion of that month's instalment.
  - `balance` — outstanding balance after that month's payment
    (never below `0.0`).

  Note: the loop iterates `range(1, tenure_months)`, i.e. months
  `1` through `tenure_months - 1`, so the schedule returned has
  `tenure_months - 1` rows rather than `tenure_months` rows. The
  `if month == tenure_months:` branch inside the loop (intended to
  handle the final instalment) is consequently unreachable given the
  loop's range.
- **Calls:** `_monthly_rate()`, `emi()`.
- **Called by:** `outstanding_after()`, `prepayment_savings()`, `cli.py:main()`.

---

### `outstanding_after(principal, annual_rate, tenure_months, months_paid)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Determines the outstanding loan balance after a given
  number of months have been paid.
- **Parameters:**
  - `principal`, `annual_rate`, `tenure_months` — loan parameters (see `emi()`).
  - `months_paid` (int) — number of EMIs already paid.
- **Returns:** `float`
  - If `months_paid <= 0`, returns the original `principal` (rounded).
  - If `months_paid` exceeds the number of rows in the schedule, returns
    `0.0`.
  - Otherwise returns the `balance` value from the schedule row at index
    `months_paid - 1`.
- **Calls:** `amortisation_schedule()`.
- **Called by:** none within the codebase (not referenced elsewhere).

---

### `remaining_tenure(balance, annual_rate, instalment)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Given an outstanding balance, an annual rate, and a fixed
  instalment amount, calculates how many more months are needed to fully
  repay the balance.
- **Parameters:**
  - `balance` (number) — outstanding principal balance.
  - `annual_rate` (number) — annual interest rate as a percentage.
  - `instalment` (number) — the fixed monthly instalment being paid.
- **Returns:** `int`
  - If `balance <= 0`, returns `0`.
  - If the (monthly, decimal) rate `r = annual_rate / 100` is `0`, returns
    `ceil(balance / instalment)`.
  - If `instalment <= balance * r`, raises
    `ValueError("instalment too small to repay the loan")` (the
    instalment would never cover the interest, so the loan could never be
    repaid).
  - Otherwise returns `ceil(n)` where `n` is derived from the standard
    loan-tenure logarithmic formula.

  Note: `r` here is computed as `annual_rate / 100` (annual decimal
  rate), not divided by `1200`/12 as in `_monthly_rate()`. This differs
  from the monthly-rate convention used elsewhere in the module.
- **Calls:** `math.ceil()`, `math.log()` (standard library).
- **Called by:** `prepayment_savings()`.

---

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** "Keep the same EMI after a lump-sum prepayment and shorten
  the tenure." Calculates how much interest and time is saved if a
  borrower makes a one-time lump-sum prepayment at a given month while
  continuing to pay the original EMI.
- **Parameters:**
  - `principal`, `annual_rate`, `tenure_months` — original loan
    parameters.
  - `prepay_month` (int) — the month at which the lump-sum prepayment is
    made.
  - `prepay_amount` (number) — the lump-sum amount paid towards the
    principal at `prepay_month`.
- **Returns:** `dict` with keys:
  - `emi` — the (unchanged) EMI amount.
  - `months_saved` — difference between the originally remaining tenure
    and the new remaining tenure after prepayment.
  - `new_tenure` — `prepay_month + months_left`, the new total tenure in
    months.
  - `interest_saved` — difference between original total interest and
    new total interest, rounded to 2 decimals.
  - `interest_paid_before_prepayment` — sum of interest paid in all
    months up to `prepay_month`, rounded to 2 decimals.
- **Calls:** `emi()`, `amortisation_schedule()`, `remaining_tenure()`,
  `total_interest()`.
- **Called by:** `cli.py:main()`.

---

### `compare_offers(principal, offers)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Compares multiple loan offers for the same principal and
  ranks them by total cost (interest + processing fee).
- **Parameters:**
  - `principal` (number) — loan principal, common to all offers.
  - `offers` (list[dict]) — each offer dict must contain `bank`, `rate`,
    `tenure`, and may optionally contain `processing_fee_pct` (defaults
    to `0`).
- **Returns:** `list[dict]`, one entry per offer, sorted ascending by
  `total_cost`, each with keys:
  - `bank`, `emi`, `total_interest`, `processing_fee`, `total_cost`.
- **Calls:** `emi()`, `total_interest()`.
- **Called by:** none within the codebase (not invoked from `cli.py`).

---

### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Estimates the maximum loan principal a borrower is
  eligible for, based on their monthly income, existing EMI obligations,
  and a Fixed Obligation to Income Ratio (FOIR) cap.
- **Parameters:**
  - `monthly_income` (number) — borrower's gross monthly income.
  - `existing_emis` (number) — sum of EMIs the borrower is already paying
    on other loans.
  - `annual_rate` (number) — annual interest rate as a percentage for the
    new loan.
  - `tenure_months` (int) — proposed tenure in months for the new loan.
  - `foir` (float, optional, default `0.5`) — the maximum fraction of
    monthly income that may go towards all EMIs combined.
- **Returns:** `float`
  - Computes `available = monthly_income * foir - existing_emis`.
  - If `available <= 0`, returns `0.0` (borrower not eligible).
  - If the monthly rate is `0`, returns `available * tenure_months`.
  - Otherwise returns the maximum principal supportable by `available`
    as a monthly instalment, using the inverse of the EMI formula:
    `available * ((1+r)^n - 1) / (r * (1+r)^n)`, rounded to 2 decimals.
- **Calls:** `_monthly_rate()`.
- **Called by:** none within the codebase (not invoked from `cli.py`).

---

### `format_inr(amount)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Formats a numeric amount as an Indian Rupee currency
  string using Indian digit grouping (2-digit groups after the initial
  3-digit group, e.g. `₹12,34,567.89`), prefixed with `₹` and a leading
  `-` for negative amounts.
- **Parameters:**
  - `amount` (number) — the amount to format (may be negative).
- **Returns:** `str` — the formatted currency string, e.g.
  `"₹10,00,000.00"`.
- **Calls:** none (built-in `round`, string formatting only).
- **Called by:** `summary()`.

---

### `schedule_to_csv(rows, path)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Writes an amortisation schedule (as produced by
  `amortisation_schedule()`) to a CSV file.
- **Parameters:**
  - `rows` (list[dict]) — schedule rows, each expected to have `month`,
    `emi`, `interest`, `principal`, `balance` keys.
  - `path` (str) — filesystem path to write the CSV file to.
- **Returns:** `None`. Performs file I/O: opens `path` for writing,
  writes a header row (`month,emi,interest,principal,balance`), then one
  comma-separated line per row.
- **Calls:** none (uses built-in `open`).
- **Called by:** none within the codebase (not invoked from `cli.py`).
  This is the only function in the module that performs file I/O / has a
  side effect. Note that `summary()` is also not strictly pure, since it
  defaults to `date.today()` when no `start` is supplied (see the
  `summary()` entry below and the note in Section 1).

---

### `summary(principal, annual_rate, tenure_months, start=None)`
- **Module:** `loan_calc/calculator.py`
- **Purpose:** Produces a human-readable summary of a loan: formatted
  principal, rate, tenure, EMI, total interest, total payment, and the
  expected date of the last EMI.
- **Parameters:**
  - `principal`, `annual_rate`, `tenure_months` — loan parameters (see
    `emi()`).
  - `start` (`datetime.date`, optional) — the date the loan starts/first
    EMI is due. Defaults to `date.today()` if not supplied.
- **Returns:** `dict` with keys:
  - `principal` — formatted principal (via `format_inr`).
  - `rate` — e.g. `"9% p.a."`.
  - `tenure` — e.g. `"240 months"`.
  - `emi` — formatted EMI amount.
  - `total_interest` — formatted total interest.
  - `total_payment` — formatted total payment.
  - `last_emi` — year-month string (`YYYY-MM`) of the final instalment,
    computed by adding `tenure_months` to `start`.
  - `currency` — always `DEFAULT_CURRENCY` ("INR").
- **Calls:** `emi()`, `total_interest()`, `total_payment()`,
  `format_inr()`.
- **Called by:** `cli.py:main()`.

---

### `main()`
- **Module:** `cli.py`
- **Purpose:** The CLI entry point. Parses command-line arguments and
  drives the calculation/printing workflow.
- **Parameters:** none (reads from `sys.argv` via `argparse`).
- **Returns:** `None`. Prints results to stdout.
- **Behaviour:**
  1. Builds an `argparse.ArgumentParser` accepting positional arguments
     `principal` (float), `rate` (float, annual % ), `tenure` (int,
     months), and optional flags `--schedule` (boolean flag),
     `--prepay-month` (int), `--prepay-amount` (float).
  2. Always calls `summary(principal, rate, tenure)` and prints the
     result as indented JSON.
  3. If `--schedule` was passed, calls `amortisation_schedule(principal,
     rate, tenure)` and prints each row dict on its own line (not JSON
     — uses Python's default dict `repr`/`str` via `print(row)`).
  4. If both `--prepay-month` and `--prepay-amount` were supplied (and
     both are truthy — note: a prepay month/amount of `0` would be
     treated as "not supplied" due to the truthy check), calls
     `prepayment_savings(principal, rate, tenure, prepay_month,
     prepay_amount)` and prints the result as indented JSON.
- **Calls:** `summary()`, `amortisation_schedule()`, `prepayment_savings()`.
- **Called by:** the `if __name__ == "__main__":` guard at the bottom of
  `cli.py`, i.e. invoked automatically when `cli.py` is run as a script.

## 4. Function interaction map

```
_monthly_rate()
  ├── called by: emi()
  ├── called by: amortisation_schedule()
  └── called by: eligible_amount()

emi()
  ├── calls: _monthly_rate()
  ├── called by: total_payment()
  ├── called by: amortisation_schedule()
  ├── called by: prepayment_savings()
  ├── called by: compare_offers()
  └── called by: summary()

total_payment()
  ├── calls: emi()
  ├── called by: total_interest()
  └── called by: summary()

total_interest()
  ├── calls: total_payment()
  ├── called by: prepayment_savings()
  ├── called by: compare_offers()
  └── called by: summary()

amortisation_schedule()
  ├── calls: _monthly_rate(), emi()
  ├── called by: outstanding_after()
  ├── called by: prepayment_savings()
  └── called by: cli.main()  (when --schedule is passed)

outstanding_after()
  └── calls: amortisation_schedule()
      (not called elsewhere in the codebase)

remaining_tenure()
  └── called by: prepayment_savings()

prepayment_savings()
  ├── calls: emi(), amortisation_schedule(), remaining_tenure(), total_interest()
  └── called by: cli.main()  (when --prepay-month and --prepay-amount are passed)

compare_offers()
  └── calls: emi(), total_interest()
      (not called elsewhere in the codebase)

eligible_amount()
  └── calls: _monthly_rate()
      (not called elsewhere in the codebase)

format_inr()
  └── called by: summary()

schedule_to_csv()
  (standalone; not called elsewhere in the codebase)

summary()
  ├── calls: emi(), total_interest(), total_payment(), format_inr()
  └── called by: cli.main()

cli.main()
  └── calls: summary(), amortisation_schedule(), prepayment_savings()
```

## 5. Execution flow (CLI input → calculation → output)

1. **Invocation:** The user runs `python cli.py <principal> <rate>
   <tenure> [--schedule] [--prepay-month N] [--prepay-amount X]` from the
   command line.
2. **Argument parsing:** `cli.py`'s `main()` builds an `argparse`
   parser and parses `sys.argv` into the namespace `a`, giving typed
   values for `principal` (float), `rate` (float), `tenure` (int), and
   optional `schedule`, `prepay_month`, `prepay_amount`.
3. **Summary calculation (always runs):**
   - `summary(a.principal, a.rate, a.tenure)` is called.
   - Internally, `summary()` calls `emi()` (which itself calls
     `_monthly_rate()`), `total_interest()` (which calls
     `total_payment()`, which calls `emi()` again), `total_payment()`
     again directly, and `format_inr()` to format each numeric value for
     display.
   - The resulting dict is serialized with `json.dumps(..., indent=2,
     ensure_ascii=False)` and printed to stdout.
4. **Optional amortisation schedule (`--schedule` flag):**
   - If set, `amortisation_schedule(a.principal, a.rate, a.tenure)` is
     called, which internally calls `_monthly_rate()` and `emi()` to
     build a list of per-month dicts (interest/principal/balance
     breakdown).
   - Each row dict is printed on its own line via `print(row)` (plain
     Python dict representation, not JSON).
5. **Optional prepayment analysis (`--prepay-month` and
   `--prepay-amount` flags):**
   - If both are supplied, `prepayment_savings(a.principal, a.rate,
     a.tenure, a.prepay_month, a.prepay_amount)` is called.
   - Internally this calls `emi()`, `amortisation_schedule()`,
     `remaining_tenure()`, and `total_interest()` to compute the
     months/interest saved by the prepayment.
   - The resulting dict is serialized with `json.dumps(..., indent=2)`
     and printed to stdout.
6. **Exit:** After all requested outputs are printed, `main()` returns
   and the script exits normally.

Functions such as `outstanding_after()`, `compare_offers()`,
`eligible_amount()`, and `schedule_to_csv()` exist in `calculator.py` but
are **not currently wired into `cli.py`** — they are part of the public
API (exported via `loan_calc/__init__.py`) but have no CLI entry point in
the current codebase.
