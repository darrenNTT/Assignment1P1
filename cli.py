import argparse
import json

from loan_calc import amortisation_schedule, prepayment_savings, summary


def main() -> None:
    """
    CLI entry point for the loan calculator.

    Parses command-line arguments (principal, rate, tenure, and optional
    --schedule, --prepay-month, --prepay-amount flags), then prints:
      - A loan summary (always, as indented JSON).
      - The amortisation schedule (if --schedule is passed), one row per line.
      - Prepayment savings (if both --prepay-month and --prepay-amount are
        passed), as indented JSON.

    Returns:
        None. All output is printed to stdout.
    """
    ap = argparse.ArgumentParser(description="Loan calculator")
    ap.add_argument("principal", type=float)
    ap.add_argument("rate", type=float, help="annual interest rate in %")
    ap.add_argument("tenure", type=int, help="tenure in months")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--prepay-month", type=int)
    ap.add_argument("--prepay-amount", type=float)
    a = ap.parse_args()

    print(json.dumps(summary(a.principal, a.rate, a.tenure), indent=2, ensure_ascii=False))
    if a.schedule:
        for row in amortisation_schedule(a.principal, a.rate, a.tenure):
            print(row)
    if a.prepay_month and a.prepay_amount:
        print(json.dumps(prepayment_savings(a.principal, a.rate, a.tenure, a.prepay_month, a.prepay_amount), indent=2))


if __name__ == "__main__":
    main()
