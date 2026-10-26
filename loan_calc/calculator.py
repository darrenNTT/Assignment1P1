import math
from datetime import date
from typing import List, Dict, Optional

from .exceptions import (
    InvalidPrincipalError,
    InvalidRateError,
    InvalidTenureError,
    InvalidInstalmentError,
    InvalidPrepaymentError,
    InvalidIncomeError,
)


DEFAULT_CURRENCY = "INR"


def _is_number(value) -> bool:
    """Return True if value is an int or float, excluding bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    """Return True if value is a number and not NaN or +/-infinity."""
    return _is_number(value) and not math.isnan(value) and not math.isinf(value)


def _is_strict_int(value) -> bool:
    """
    Return True if value is a strict int (not bool, and not a float,
    even a whole-number float like 12.0).

    Whole-number floats are intentionally rejected: tenure/month-count
    parameters validated with this check are later used in contexts
    requiring a true int (e.g. range(), list indexing), where a float
    (even 12.0) raises a TypeError. Rejecting floats here keeps
    validation consistent with actual usage.
    """
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def _monthly_rate(annual_rate):
    r = annual_rate / 1200
    return r


def emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Calculate the Equated Monthly Instalment (EMI) for a loan.

    Uses the standard amortising-loan formula. Returns principal divided
    evenly across the tenure if the computed monthly interest rate is zero.

    Args:
        principal: Loan principal amount. Must be greater than 0.
        annual_rate: Annual interest rate as a percentage (e.g. 9 for 9%).
        tenure_months: Loan tenure in months. Must be greater than 0.

    Returns:
        The EMI amount, rounded to 2 decimal places.

    Raises:
        InvalidPrincipalError: If principal is not a finite positive number.
        InvalidRateError: If annual_rate is not a finite non-negative number.
        InvalidTenureError: If tenure_months is not a positive integer.
    """
    if not _is_finite_number(principal) or principal <= 0:
        raise InvalidPrincipalError("principal must be a finite positive number")
    if not _is_finite_number(annual_rate) or annual_rate < 0:
        raise InvalidRateError("annual_rate must be a finite non-negative number")
    if not _is_strict_int(tenure_months) or tenure_months <= 0:
        raise InvalidTenureError("tenure_months must be a positive integer")
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(principal / tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(principal * r * f / (f - 1), 2)


def total_payment(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Calculate the total amount repaid over the full loan tenure.

    Args:
        principal: Loan principal amount.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Loan tenure in months.

    Returns:
        The total of all EMIs paid over the tenure (EMI multiplied by the
        number of months), rounded to 2 decimal places.
    """
    return round(emi(principal, annual_rate, tenure_months) * tenure_months, 2)


def total_interest(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Calculate the total interest paid over the loan tenure.

    Args:
        principal: Loan principal amount.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Loan tenure in months.

    Returns:
        Total interest paid (total payment minus principal), rounded to
        2 decimal places.
    """
    return round(total_payment(principal, annual_rate, tenure_months) - principal, 2)


def amortisation_schedule(principal: float, annual_rate: float, tenure_months: int) -> List[Dict]:
    """
    Build the month-by-month amortisation schedule for a loan.

    For each scheduled month, computes how the EMI splits into interest
    and principal portions, and the outstanding balance remaining after
    that payment.

    Args:
        principal: Loan principal amount.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Loan tenure in months.

    Returns:
        A list of dicts, one per scheduled month, each containing:
            month (int): The month number (1-indexed).
            emi (float): The instalment amount for that month.
            interest (float): The interest portion of that month's instalment.
            principal (float): The principal portion of that month's instalment.
            balance (float): The outstanding balance after that month's payment.
    """
    r = _monthly_rate(annual_rate)
    instalment = emi(principal, annual_rate, tenure_months)
    balance = principal
    rows = []
    for month in range(1, tenure_months + 1):
        interest = round(balance * r, 2)
        principal_part = round(instalment - interest, 2)
        if month == tenure_months:
            principal_part = round(balance, 2)
            instalment_amt = round(principal_part + interest, 2)
        else:
            instalment_amt = instalment
        balance = round(balance - principal_part, 2)
        rows.append({
            "month": month,
            "emi": instalment_amt,
            "interest": interest,
            "principal": principal_part,
            "balance": max(balance, 0.0),
        })
    return rows


def outstanding_after(principal: float, annual_rate: float, tenure_months: int, months_paid: int) -> float:
    """
    Determine the outstanding loan balance after a given number of months paid.

    Args:
        principal: Loan principal amount.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Loan tenure in months.
        months_paid: Number of EMIs already paid.

    Returns:
        The outstanding balance as a float. Returns the original principal
        (rounded) if months_paid is 0 or negative, and 0.0 if months_paid
        exceeds the number of scheduled payments.

    Raises:
        InvalidTenureError: If months_paid is not an integer.
    """
    if not _is_strict_int(months_paid):
        raise InvalidTenureError("months_paid must be an integer")
    if months_paid <= 0:
        return round(principal, 2)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    if months_paid > len(sched):
        return 0.0
    return sched[months_paid - 1]["balance"]


def remaining_tenure(balance: float, annual_rate: float, instalment: float) -> int:
    """
    Calculate how many more months are needed to fully repay a balance.

    Args:
        balance: Outstanding principal balance.
        annual_rate: Annual interest rate as a percentage.
        instalment: The fixed monthly instalment amount being paid.

    Returns:
        The number of months needed to repay the balance (rounded up), or
        0 if the balance is already zero or negative.

    Raises:
        InvalidInstalmentError: If instalment is not a finite positive
            number, or is too small to ever cover the interest portion
            of the balance (i.e. the loan could never be repaid).
        InvalidRateError: If annual_rate is not a finite non-negative
            number.

    Note:
        A negative or zero balance is NOT an error — it is intentional,
        existing behavior meaning the loan is already fully repaid (or
        overpaid), so 0 months remain. Only balance's *type* is
        validated; its sign is not.
    """
    if not _is_finite_number(balance):
        raise InvalidInstalmentError("balance must be a finite number")
    if not _is_finite_number(annual_rate) or annual_rate < 0:
        raise InvalidRateError("annual_rate must be a finite non-negative number")
    if not _is_finite_number(instalment) or instalment <= 0:
        raise InvalidInstalmentError("instalment must be a finite positive number")
    r = annual_rate / 1200
    if balance <= 0:
        return 0
    if r == 0:
        return math.ceil(balance / instalment)
    if instalment <= balance * r:
        raise InvalidInstalmentError("instalment too small to repay the loan")
    n = -math.log(1 - balance * r / instalment) / math.log(1 + r)
    # Round to remove floating-point noise (e.g. 18.000047907513988
    # instead of exactly 18.0) before taking the ceiling, so values that
    # are mathematically whole numbers are not incorrectly rounded up to
    # the next integer due to tiny precision errors in the log-based
    # formula. 4 decimal places is enough to absorb the observed noise
    # (which is usually << 1e-4) while still preserving genuinely
    # fractional results (e.g. 5.0001 still correctly ceils to 6).
    return math.ceil(round(n, 4))


def prepayment_savings(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepay_month: int,
    prepay_amount: float,
) -> Dict:
    """
    Keep the same EMI after a lump-sum prepayment and shorten the tenure.

    Calculates how much interest and time is saved if a borrower makes a
    one-time lump-sum prepayment at a given month while continuing to pay
    the original EMI amount.

    Args:
        principal: Original loan principal amount.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Original loan tenure in months.
        prepay_month: The month at which the lump-sum prepayment is made.
        prepay_amount: The lump-sum amount paid towards the principal at
            prepay_month.

    Returns:
        A dict containing:
            emi (float): The unchanged EMI amount.
            months_saved (int): Months saved compared to the original tenure.
            new_tenure (int): The new total tenure in months after prepayment.
            interest_saved (float): Interest saved, rounded to 2 decimal places.
            interest_paid_before_prepayment (float): Interest paid up to
                prepay_month, rounded to 2 decimal places.

    Raises:
        InvalidPrepaymentError: If prepay_month is not an integer within
            [1, tenure_months], or if prepay_amount is not a finite
            non-negative number.

    Note:
        A prepay_amount that exceeds the outstanding balance at
        prepay_month is NOT an error — it is intentional, existing
        behavior meaning the loan is fully paid off at that point.
    """
    if not _is_strict_int(prepay_month) or prepay_month < 1 or prepay_month > tenure_months:
        raise InvalidPrepaymentError(
            "prepay_month must be an integer between 1 and tenure_months"
        )
    if not _is_finite_number(prepay_amount) or prepay_amount < 0:
        raise InvalidPrepaymentError("prepay_amount must be a finite non-negative number")
    instalment = emi(principal, annual_rate, tenure_months)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    balance = sched[prepay_month - 1]["balance"]
    new_balance = balance - prepay_amount
    if new_balance <= 0:
        months_left = 0
    else:
        months_left = remaining_tenure(new_balance, annual_rate, instalment)
    original_left = tenure_months - prepay_month
    interest_paid_so_far = sum(row["interest"] for row in sched[:prepay_month])
    original_interest = total_interest(principal, annual_rate, tenure_months)
    # Cap the amount used in the financial calculation to the actual
    # outstanding balance: any portion of prepay_amount exceeding the
    # balance is not actually "spent" on the loan (there is nothing left
    # to prepay), so including it in new_total would overstate the total
    # amount paid and produce a nonsensical, deeply negative
    # interest_saved. The loan is simply fully repaid at prepay_month in
    # that case.
    effective_prepay_amount = min(prepay_amount, balance)
    new_total = instalment * prepay_month + effective_prepay_amount + instalment * months_left
    new_interest = new_total - principal
    return {
        "emi": instalment,
        "months_saved": original_left - months_left,
        "new_tenure": prepay_month + months_left,
        "interest_saved": round(original_interest - new_interest, 2),
        "interest_paid_before_prepayment": round(interest_paid_so_far, 2),
    }


def compare_offers(principal: float, offers: List[Dict]) -> List[Dict]:
    """
    Compare multiple loan offers for the same principal and rank by total cost.

    Args:
        principal: Loan principal amount, common to all offers.
        offers: A list of offer dicts. Each dict must contain "bank" (str),
            "rate" (float, annual %), and "tenure" (int, months), and may
            optionally contain "processing_fee_pct" (float, defaults to 0).

    Returns:
        A list of dicts, one per offer, sorted ascending by total_cost,
        each containing: bank, emi, total_interest, processing_fee,
        total_cost.
    """
    out = []
    for o in offers:
        e = emi(principal, o["rate"], o["tenure"])
        ti = total_interest(principal, o["rate"], o["tenure"])
        fee = o.get("processing_fee_pct", 0) * principal / 100
        out.append({
            "bank": o["bank"],
            "emi": e,
            "total_interest": ti,
            "processing_fee": round(fee, 2),
            "total_cost": round(ti + fee, 2),
        })
    out.sort(key=lambda x: x["total_cost"])
    return out


def eligible_amount(
    monthly_income: float,
    existing_emis: float,
    annual_rate: float,
    tenure_months: int,
    foir: float = 0.5,
) -> float:
    """
    Estimate the maximum loan principal a borrower is eligible for.

    Based on the borrower's monthly income, existing EMI obligations, and a
    Fixed Obligation to Income Ratio (FOIR) cap.

    Args:
        monthly_income: Borrower's gross monthly income.
        existing_emis: Sum of EMIs the borrower is already paying on other loans.
        annual_rate: Annual interest rate as a percentage for the new loan.
        tenure_months: Proposed tenure in months for the new loan.
        foir: Maximum fraction of monthly income that may go towards all
            EMIs combined. Defaults to 0.5.

    Returns:
        The maximum eligible principal, rounded to 2 decimal places.
        Returns 0.0 if the borrower has no available income capacity.

    Raises:
        InvalidIncomeError: If monthly_income is not a finite positive
            number, existing_emis is not a finite non-negative number,
            or foir is not a finite number within (0, 1].
        InvalidRateError: If annual_rate is not a finite non-negative
            number.
        InvalidTenureError: If tenure_months is not a positive integer.
    """
    if not _is_finite_number(monthly_income) or monthly_income <= 0:
        raise InvalidIncomeError("monthly_income must be a finite positive number")
    if not _is_finite_number(existing_emis) or existing_emis < 0:
        raise InvalidIncomeError("existing_emis must be a finite non-negative number")
    if not _is_finite_number(foir) or foir <= 0 or foir > 1:
        raise InvalidIncomeError("foir must be a finite number within (0, 1]")
    if not _is_finite_number(annual_rate) or annual_rate < 0:
        raise InvalidRateError("annual_rate must be a finite non-negative number")
    if not _is_strict_int(tenure_months) or tenure_months <= 0:
        raise InvalidTenureError("tenure_months must be a positive integer")
    available = monthly_income * foir - existing_emis
    if available <= 0:
        return 0.0
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(available * tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(available * (f - 1) / (r * f), 2)


def format_inr(amount: float) -> str:
    """
    Format a numeric amount as an Indian Rupee currency string.

    Uses Indian digit grouping (2-digit groups after the initial 3-digit
    group), prefixed with the rupee symbol, with a leading "-" for
    negative amounts.

    Args:
        amount: The amount to format. May be negative.

    Returns:
        The formatted currency string, e.g. "₹10,00,000.00".
    """
    neg = amount < 0
    amount = abs(round(amount, 2))
    whole, frac = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "₹" + whole + "." + frac


def schedule_to_csv(rows: List[Dict], path: str) -> None:
    """
    Write an amortisation schedule to a CSV file.

    Args:
        rows: Schedule rows as produced by amortisation_schedule(), each
            expected to have "month", "emi", "interest", "principal", and
            "balance" keys.
        path: Filesystem path to write the CSV file to.

    Returns:
        None. Writes a header row followed by one comma-separated line per
        schedule row to the file at `path`.
    """
    with open(path, "w") as fh:
        fh.write("month,emi,interest,principal,balance\n")
        for r in rows:
            fh.write(f'{r["month"]},{r["emi"]},{r["interest"]},{r["principal"]},{r["balance"]}\n')


def summary(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    start: Optional[date] = None,
) -> Dict:
    """
    Produce a human-readable summary of a loan.

    Includes formatted principal, rate, tenure, EMI, total interest, total
    payment, and the expected year-month of the last EMI.

    Args:
        principal: Loan principal amount.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Loan tenure in months.
        start: The date the loan starts / first EMI is due. Defaults to
            today's date if not supplied. Note: when not supplied, the
            output of this function depends on the current date.

    Returns:
        A dict containing: principal, rate, tenure, emi, total_interest,
        total_payment, last_emi (formatted as "YYYY-MM"), and currency.
    """
    start = start or date.today()
    e = emi(principal, annual_rate, tenure_months)
    end_year = start.year + (start.month - 1 + tenure_months) // 12
    end_month = (start.month - 1 + tenure_months) % 12 + 1
    return {
        "principal": format_inr(principal),
        "rate": f"{annual_rate}% p.a.",
        "tenure": f"{tenure_months} months",
        "emi": format_inr(e),
        "total_interest": format_inr(total_interest(principal, annual_rate, tenure_months)),
        "total_payment": format_inr(total_payment(principal, annual_rate, tenure_months)),
        "last_emi": f"{end_year}-{end_month:02d}",
        "currency": DEFAULT_CURRENCY,
    }
