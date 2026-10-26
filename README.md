# loan-calc (Assignment P1)

A small Python module for retail loan calculations: EMI, amortisation schedule, prepayment savings, offer comparison and eligibility.

This project started with no tests and no documentation, and with several known calculation bugs. Assignment P1 has been completed:

- **Documentation**: see `ARCHITECTURE.md` for a full breakdown of the module's architecture, every function's purpose/parameters/return values, and the execution flow from CLI input to output.
- **Tests**: a full pytest suite lives in the `tests/` folder (`test_calculator.py`, `test_cli.py`, `test_exceptions.py`), covering normal cases, edge cases, and input validation, with 99%+ line coverage.
- **Bug fixes**: three identified calculation bugs (an off-by-one error in the amortisation schedule, an incorrect interest-rate conversion in `remaining_tenure()`, and premature rounding in the monthly rate calculation) have been fixed and verified with regression tests.
- **Input validation**: public functions now validate their inputs and raise a custom exception hierarchy (`LoanCalculatorError` and its subclasses, all also `ValueError` for backward compatibility) instead of producing incorrect results or raw `TypeError`/`ValueError` on invalid input.

See `PROMPT_LOG.md` for the full development history, including the design decisions, bugs found, and fixes applied.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Try it

```bash
python cli.py 1000000 9 240
python cli.py 1000000 9 240 --schedule
python cli.py 1000000 9 240 --prepay-month 24 --prepay-amount 200000
```

## Run tests

```bash
pytest --cov=loan_calc --cov=cli --cov-report=term-missing
```

The full test suite is in the `tests/` folder.
