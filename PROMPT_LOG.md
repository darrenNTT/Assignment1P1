# Prompt Log

This file records prompts sent to the AI assistant and the responses/actions taken, for reference and audit purposes.

---

## Entry 1 — 2026-10-25

### Prompt

```
Analyse the existing Python code in my loan-calc workspace and create a file named ARCHITECTURE.md in the project root.

The document should include:

1. An overview of the loan calculator's architecture.
2. Every function defined across the Python files, including helper functions.
3. Each function's purpose, parameters, and return values.
4. How the functions interact with one another.
5. The overall execution flow, from CLI input to calculation and output.

Base the documentation strictly on the existing source code.

Do not modify any existing Python files, fix bugs, or implement improvements yet. Only create ARCHITECTURE.md.
```

### Response

The assistant analyzed the Python source files in the workspace (`cli.py`, `loan_calc/__init__.py`, `loan_calc/calculator.py`) without modifying any of them, and created `loan-calc/ARCHITECTURE.md` documenting:

1. **Overview** — Described the project structure (`cli.py` as a thin argparse-based CLI, `loan_calc/` package containing all business logic in `calculator.py`, re-exported via `__init__.py`). Noted there is no persistent state/DB/network I/O, and all functions are pure except `schedule_to_csv()`.
2. **Modules** — Documented `loan_calc/__init__.py`, `loan_calc/calculator.py` (including the `DEFAULT_CURRENCY = "INR"` constant), and `cli.py`.
3. **Function reference** — A detailed entry for every function found in the codebase, each including purpose, parameters, return values, and calls/called-by relationships:
   - `_monthly_rate()`
   - `emi()`
   - `total_payment()`
   - `total_interest()`
   - `amortisation_schedule()` (noted a bug: loop range produces `tenure_months - 1` rows instead of `tenure_months`, making the final-instalment branch unreachable)
   - `outstanding_after()`
   - `remaining_tenure()` (noted it uses `annual_rate / 100` rather than the `_monthly_rate()` convention of `/1200`)
   - `prepayment_savings()`
   - `compare_offers()`
   - `eligible_amount()`
   - `format_inr()`
   - `schedule_to_csv()`
   - `summary()`
   - `main()` (in `cli.py`)
4. **Function interaction map** — An ASCII tree showing calls/called-by relationships between all functions across both modules.
5. **Execution flow** — A step-by-step walkthrough of the CLI's execution path: argument parsing → `summary()` (always runs) → optional `amortisation_schedule()` (`--schedule` flag) → optional `prepayment_savings()` (`--prepay-month`/`--prepay-amount` flags) → exit. Also flagged that `outstanding_after()`, `compare_offers()`, `eligible_amount()`, and `schedule_to_csv()` exist in `calculator.py` but are not wired into the CLI.

No Python source files were modified, no bugs were fixed, and no improvements were implemented — only `ARCHITECTURE.md` was created, as requested.

---

## Entry 2 — 2026-10-25

### Prompt

```
noticed an error in ARCHITECTURE.md, it says all functions are pure except schedule_to_csv, but summary() uses date.today() when no start date is given, so its output can change depending on the date. fix this in ARCHITECTURE.md and update PROMPT_LOG.md with this prompt, the AI mistake, why it's wrong and what was corrected. dont modify any python files.
```

### AI mistake

In the Entry 1 response, `ARCHITECTURE.md` stated (Section 1 "Overview" and
in the `schedule_to_csv()` function reference entry):

> "All functions in `calculator.py` are pure (deterministic, given the
> same inputs they return the same outputs), except `schedule_to_csv`,
> which performs file I/O."

This claim was incorrect — it missed that `summary()` is also not pure.

### Why it's wrong

In `loan_calc/calculator.py`, `summary()` is defined as:

```python
def summary(principal, annual_rate, tenure_months, start=None):
    start = start or date.today()
    ...
```

When `summary()` is called without an explicit `start` argument (which is
how `cli.py:main()` always calls it — `summary(principal, rate, tenure)`,
with no `start`), it defaults to `date.today()`. This means the `last_emi`
field of the returned dict (and therefore the dict as a whole) depends on
*when* the function happens to be called, not solely on its
`principal`/`annual_rate`/`tenure_months` arguments. Calling
`summary(100000, 9, 12)` today and calling it again a month from now would
produce different `last_emi` values despite identical explicit arguments.
This violates the definition of a pure function (same inputs → same
output every time), so the original "all functions are pure except
`schedule_to_csv`" statement was factually inaccurate.

### What was corrected

`ARCHITECTURE.md` was updated (no Python files were touched) in two places:

1. **Section 1, Overview** — rewritten to state that *most* functions are
   pure, with **two** exceptions: `schedule_to_csv` (file I/O) and
   `summary` (impure when called without an explicit `start`, due to the
   `date.today()` default), explaining the date-dependent `last_emi`
   behaviour.
2. **`schedule_to_csv()` function reference entry** — the closing note
   that previously claimed it was "the only function in the module that
   performs file I/O / has a side effect; all other functions are pure"
   was corrected to note that `summary()` is also not strictly pure for
   the same reason, with a cross-reference to the `summary()` entry and
   the Section 1 note.

No Python source files were modified; only `ARCHITECTURE.md` was edited to
fix the documentation error.

---

## Entry 3 — 2026-10-26

### Prompt

```
add docstrings and type hints to all public functions in the python files, explaining what each function does, its parameters and return values. dont change any existing logic or fix bugs yet, only add documentation and type annotations. show me the proposed changes first so i can review them before applying. also update PROMPT_LOG.md with this prompt and a summary of what was suggested.
```

### Summary of what was suggested and applied

The assistant proposed adding Google-style docstrings (Purpose / Args /
Returns / Raises) and PEP 484 type hints to every **public** function in
the codebase — i.e. all functions without a leading underscore. The
private helper `_monthly_rate()` in `loan_calc/calculator.py` was
explicitly excluded, since it is an internal implementation detail (the
user correctly flagged this when the assistant initially mis-scoped the
proposal to include it).

Each function's proposed signature and docstring was presented one at a
time in chat for individual review and approval, per the user's explicit
instruction not to write a separate summary file and not to apply changes
until each one was approved. After approval, each change was written
directly into the corresponding `.py` file using targeted edits — no
function logic, control flow, or behavior was altered in any way.

**`loan_calc/calculator.py`** — added `from typing import List, Dict,
Optional` and docstrings/type hints to:
- `emi()`
- `total_payment()`
- `total_interest()`
- `amortisation_schedule()`
- `outstanding_after()`
- `remaining_tenure()`
- `prepayment_savings()` (expanded its existing one-line docstring into a
  full Args/Returns docstring, preserving the original summary line)
- `compare_offers()`
- `eligible_amount()`
- `format_inr()`
- `schedule_to_csv()`
- `summary()` (docstring explicitly notes the `date.today()` default
  behavior flagged as impure in Entry 2)

**`cli.py`** — added a docstring and `-> None` return type hint to:
- `main()`

After all changes were applied, the CLI was re-run (`python cli.py 500000
9 240`) to confirm it still produces correct output, verifying that no
logic was broken by the documentation/type-hint additions.

---
