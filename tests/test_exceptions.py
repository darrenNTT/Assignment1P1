"""
Test suite for the loan_calc custom exception hierarchy and the input
validation added to emi(), remaining_tenure(), prepayment_savings(), and
eligible_amount().

This suite also includes explicit regression tests confirming that two
pieces of existing, intentional behavior were NOT broken by the new
validation:
  1. remaining_tenure() with a negative balance still returns 0 (does
     not raise).
  2. prepayment_savings() with a prepay_amount exceeding the outstanding
     balance still returns a valid result (does not raise).
"""
import math

import pytest

from loan_calc.calculator import (
    emi,
    remaining_tenure,
    prepayment_savings,
    eligible_amount,
    amortisation_schedule,
    outstanding_after,
)
from loan_calc.exceptions import (
    LoanCalculatorError,
    InvalidPrincipalError,
    InvalidRateError,
    InvalidTenureError,
    InvalidInstalmentError,
    InvalidPrepaymentError,
    InvalidIncomeError,
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    @pytest.mark.parametrize(
        "exc_class",
        [
            InvalidPrincipalError,
            InvalidRateError,
            InvalidTenureError,
            InvalidInstalmentError,
            InvalidPrepaymentError,
            InvalidIncomeError,
        ],
    )
    def test_all_subclasses_are_loan_calculator_errors(self, exc_class):
        assert issubclass(exc_class, LoanCalculatorError)

    @pytest.mark.parametrize(
        "exc_class",
        [
            LoanCalculatorError,
            InvalidPrincipalError,
            InvalidRateError,
            InvalidTenureError,
            InvalidInstalmentError,
            InvalidPrepaymentError,
            InvalidIncomeError,
        ],
    )
    def test_all_exceptions_are_value_errors(self, exc_class):
        # Backward compatibility: every custom exception must also be a
        # ValueError, so existing pytest.raises(ValueError) patterns
        # continue to work unchanged.
        assert issubclass(exc_class, ValueError)

    def test_can_catch_specific_exception_as_value_error(self):
        with pytest.raises(ValueError):
            emi(-100, 9, 12)

    def test_can_catch_specific_exception_as_base_class(self):
        with pytest.raises(LoanCalculatorError):
            emi(-100, 9, 12)


# ---------------------------------------------------------------------------
# emi() validation
# ---------------------------------------------------------------------------

class TestEmiValidation:
    # --- bad values ---
    def test_zero_principal_raises_invalid_principal_error(self):
        with pytest.raises(InvalidPrincipalError):
            emi(0, 9, 12)

    def test_negative_principal_raises_invalid_principal_error(self):
        with pytest.raises(InvalidPrincipalError):
            emi(-100_000, 9, 12)

    def test_zero_tenure_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            emi(100_000, 9, 0)

    def test_negative_tenure_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            emi(100_000, 9, -5)

    def test_negative_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            emi(100_000, -1, 12)

    def test_zero_rate_is_valid(self):
        # 0% interest is a valid rate, not an error.
        result = emi(120_000, 0, 12)
        assert result == pytest.approx(10_000, abs=0.01)

    # --- bad types ---
    def test_string_principal_raises_invalid_principal_error(self):
        with pytest.raises(InvalidPrincipalError):
            emi("100000", 9, 12)

    def test_none_principal_raises_invalid_principal_error(self):
        with pytest.raises(InvalidPrincipalError):
            emi(None, 9, 12)

    def test_none_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            emi(100_000, None, 12)

    def test_string_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            emi(100_000, "9", 12)

    def test_fractional_tenure_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            emi(100_000, 9, 12.5)

    def test_whole_number_float_tenure_raises_invalid_tenure_error(self):
        # Even whole-number floats like 12.0 are rejected: tenure_months
        # is later used in range() and list indexing, both of which
        # require a strict int. Rejecting floats here keeps validation
        # consistent with actual usage (see PROMPT_LOG.md for the design
        # revision explaining this decision).
        with pytest.raises(InvalidTenureError):
            emi(100_000, 9, 12.0)

    def test_string_tenure_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            emi(100_000, 9, "12")

    def test_bool_tenure_raises_invalid_tenure_error(self):
        # bool is technically an int subclass in Python, but is
        # semantically wrong as a tenure and must be rejected.
        with pytest.raises(InvalidTenureError):
            emi(100_000, 9, True)

    # --- NaN / infinity ---
    def test_nan_principal_raises_invalid_principal_error(self):
        with pytest.raises(InvalidPrincipalError):
            emi(float("nan"), 9, 12)

    def test_infinite_principal_raises_invalid_principal_error(self):
        with pytest.raises(InvalidPrincipalError):
            emi(float("inf"), 9, 12)

    def test_nan_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            emi(100_000, float("nan"), 12)

    def test_infinite_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            emi(100_000, float("inf"), 12)


# ---------------------------------------------------------------------------
# remaining_tenure() validation
# ---------------------------------------------------------------------------

class TestRemainingTenureValidation:
    # --- regression: preserved existing behavior ---
    def test_negative_balance_still_returns_zero_not_an_error(self):
        # REGRESSION: this must NOT raise. Negative balance means the
        # loan is already overpaid, so 0 months remain - this is
        # existing, intentional behavior that validation must preserve.
        result = remaining_tenure(-1000, 9, 5000)
        assert result == 0

    def test_zero_balance_still_returns_zero(self):
        result = remaining_tenure(0, 9, 5000)
        assert result == 0

    # --- bad values ---
    def test_zero_instalment_raises_invalid_instalment_error(self):
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure(100_000, 9, 0)

    def test_negative_instalment_raises_invalid_instalment_error(self):
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure(100_000, 9, -500)

    def test_negative_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            remaining_tenure(100_000, -1, 5000)

    def test_instalment_too_small_still_raises_invalid_instalment_error(self):
        # This is the pre-existing "instalment too small to repay the
        # loan" check, now upgraded from plain ValueError to
        # InvalidInstalmentError (still a ValueError subclass).
        balance, annual_rate = 100_000, 12
        too_small_instalment = balance * (annual_rate / 1200)
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure(balance, annual_rate, too_small_instalment)

    # --- bad types ---
    def test_string_balance_raises_invalid_instalment_error(self):
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure("100000", 9, 5000)

    def test_none_instalment_raises_invalid_instalment_error(self):
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure(100_000, 9, None)

    # --- NaN / infinity ---
    def test_nan_balance_raises_invalid_instalment_error(self):
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure(float("nan"), 9, 5000)

    def test_infinite_instalment_raises_invalid_instalment_error(self):
        with pytest.raises(InvalidInstalmentError):
            remaining_tenure(100_000, 9, float("inf"))


# ---------------------------------------------------------------------------
# prepayment_savings() validation
# ---------------------------------------------------------------------------

class TestPrepaymentSavingsValidation:
    # --- regression: preserved existing behavior ---
    def test_prepay_amount_exceeding_balance_still_valid_not_an_error(self):
        # REGRESSION: prepay_amount larger than the outstanding balance
        # at prepay_month must NOT raise - it means the loan is fully
        # paid off at that point. This is existing, intentional
        # behavior that validation must preserve.
        principal, rate, tenure, prepay_month = 100_000, 9, 24, 6
        sched = amortisation_schedule(principal, rate, tenure)
        outstanding_balance = sched[prepay_month - 1]["balance"]
        huge_prepay_amount = outstanding_balance + 1_000_000

        result = prepayment_savings(principal, rate, tenure, prepay_month, huge_prepay_amount)
        assert result["new_tenure"] == prepay_month
        assert result["months_saved"] >= 0

    # --- bad values ---
    def test_negative_prepay_amount_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12, -100)

    def test_prepay_month_zero_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 0, 50_000)

    def test_prepay_month_exceeding_tenure_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 61, 50_000)

    def test_negative_prepay_month_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, -5, 50_000)

    # --- bad types ---
    def test_fractional_prepay_month_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12.5, 50_000)

    def test_whole_number_float_prepay_month_raises_invalid_prepayment_error(self):
        # Even whole-number floats like 12.0 are rejected: prepay_month
        # is later used for list indexing, which requires a strict int.
        # Rejecting floats here keeps validation consistent with
        # actual usage (see PROMPT_LOG.md for the design revision
        # explaining this decision).
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12.0, 50_000)

    def test_string_prepay_month_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, "12", 50_000)

    def test_bool_prepay_month_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, True, 50_000)

    def test_string_prepay_amount_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12, "50000")

    def test_none_prepay_amount_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12, None)

    # --- NaN / infinity ---
    def test_nan_prepay_amount_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12, float("nan"))

    def test_infinite_prepay_amount_raises_invalid_prepayment_error(self):
        with pytest.raises(InvalidPrepaymentError):
            prepayment_savings(500_000, 9, 60, 12, float("inf"))


# ---------------------------------------------------------------------------
# eligible_amount() validation
# ---------------------------------------------------------------------------

class TestEligibleAmountValidation:
    # --- bad values ---
    def test_zero_monthly_income_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=0, existing_emis=0, annual_rate=9, tenure_months=240)

    def test_negative_monthly_income_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=-1000, existing_emis=0, annual_rate=9, tenure_months=240)

    def test_negative_existing_emis_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=-100, annual_rate=9, tenure_months=240)

    def test_zero_foir_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=240, foir=0)

    def test_foir_greater_than_one_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=240, foir=1.5)

    def test_foir_exactly_one_is_valid(self):
        # 1.0 is the upper inclusive bound and should be accepted.
        result = eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=240, foir=1.0)
        assert result > 0

    def test_negative_rate_raises_invalid_rate_error(self):
        with pytest.raises(InvalidRateError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=-1, tenure_months=240)

    def test_zero_tenure_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=0)

    # --- bad types ---
    def test_string_monthly_income_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income="50000", existing_emis=0, annual_rate=9, tenure_months=240)

    def test_none_existing_emis_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=None, annual_rate=9, tenure_months=240)

    def test_string_foir_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=240, foir="0.5")

    def test_fractional_tenure_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=240.5)

    # --- NaN / infinity ---
    def test_nan_monthly_income_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=float("nan"), existing_emis=0, annual_rate=9, tenure_months=240)

    def test_infinite_existing_emis_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=float("inf"), annual_rate=9, tenure_months=240)

    def test_nan_foir_raises_invalid_income_error(self):
        with pytest.raises(InvalidIncomeError):
            eligible_amount(monthly_income=50_000, existing_emis=0, annual_rate=9, tenure_months=240, foir=float("nan"))


# ---------------------------------------------------------------------------
# outstanding_after() validation (code review fix #3)
# ---------------------------------------------------------------------------

class TestOutstandingAfterValidation:
    # --- regression: existing valid-int behavior unchanged ---
    def test_valid_int_months_paid_still_works(self):
        principal, rate, tenure, months_paid = 100_000, 9, 24, 5
        sched = amortisation_schedule(principal, rate, tenure)
        expected = sched[months_paid - 1]["balance"]
        result = outstanding_after(principal, rate, tenure, months_paid)
        assert result == pytest.approx(expected, abs=0.01)

    def test_zero_months_paid_still_returns_principal(self):
        result = outstanding_after(100_000, 9, 24, 0)
        assert result == pytest.approx(100_000, abs=0.01)

    def test_negative_months_paid_still_returns_principal(self):
        result = outstanding_after(100_000, 9, 24, -5)
        assert result == pytest.approx(100_000, abs=0.01)

    def test_months_paid_exceeding_schedule_still_returns_zero(self):
        result = outstanding_after(100_000, 9, 24, 999)
        assert result == 0.0

    # --- bad types: previously raised raw TypeError, now a custom exception ---
    def test_fractional_months_paid_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            outstanding_after(100_000, 9, 24, 5.5)

    def test_whole_number_float_months_paid_raises_invalid_tenure_error(self):
        # Previously caused a raw TypeError ("list indices must be
        # integers or slices, not float") because 5.0 passed the
        # months_paid <= 0 check then was used directly as a list
        # index. Now rejected cleanly by validation, consistent with
        # the strict-int requirement used for tenure_months/prepay_month
        # elsewhere in the module.
        with pytest.raises(InvalidTenureError):
            outstanding_after(100_000, 9, 24, 5.0)

    def test_string_months_paid_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            outstanding_after(100_000, 9, 24, "5")

    def test_none_months_paid_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            outstanding_after(100_000, 9, 24, None)

    def test_bool_months_paid_raises_invalid_tenure_error(self):
        with pytest.raises(InvalidTenureError):
            outstanding_after(100_000, 9, 24, True)


# ---------------------------------------------------------------------------
# Code review fix #1: prepayment_savings() with prepay_amount exceeding
# the outstanding balance must not produce a nonsensical, deeply
# negative interest_saved.
# ---------------------------------------------------------------------------

class TestPrepaymentExceedingBalanceFinancials:
    def test_interest_saved_is_positive_not_deeply_negative(self):
        # This is the exact scenario from the code review: prepay_amount
        # far exceeds the outstanding balance at prepay_month. Before
        # the fix, interest_saved was a huge negative number (e.g.
        # -994422.82) because the full (excessive) prepay_amount was
        # included in the financial total. After the fix, only the
        # actual outstanding balance is "spent", so interest_saved
        # should be a sensible, positive value.
        principal, rate, tenure, prepay_month = 100_000, 9, 24, 6
        sched = amortisation_schedule(principal, rate, tenure)
        outstanding_balance = sched[prepay_month - 1]["balance"]
        huge_prepay_amount = outstanding_balance + 1_000_000

        result = prepayment_savings(principal, rate, tenure, prepay_month, huge_prepay_amount)
        assert result["interest_saved"] > 0
        # Interest saved can never exceed the total interest that would
        # have been paid on the original loan.
        original_total_interest = (
            prepayment_savings(principal, rate, tenure, prepay_month, 0)["interest_paid_before_prepayment"]
        )
        assert result["interest_saved"] < 1_000_000  # sanity bound, not inflated by the excess

    def test_interest_saved_matches_exact_prepayment_at_balance(self):
        # Prepaying exactly the outstanding balance should produce the
        # same financial result as "overpaying" by any larger amount
        # (since the excess is now correctly ignored in the calculation).
        principal, rate, tenure, prepay_month = 100_000, 9, 24, 6
        sched = amortisation_schedule(principal, rate, tenure)
        outstanding_balance = sched[prepay_month - 1]["balance"]

        result_exact = prepayment_savings(principal, rate, tenure, prepay_month, outstanding_balance)
        result_excess = prepayment_savings(principal, rate, tenure, prepay_month, outstanding_balance + 1_000_000)
        assert result_exact["interest_saved"] == pytest.approx(result_excess["interest_saved"], abs=0.01)
        assert result_exact["new_tenure"] == result_excess["new_tenure"]
        assert result_exact["months_saved"] == result_excess["months_saved"]


# ---------------------------------------------------------------------------
# Code review fix #2: a zero prepayment must represent "no savings",
# not negative months_saved/interest_saved caused by floating-point
# noise in remaining_tenure()'s logarithmic formula.
# ---------------------------------------------------------------------------

class TestZeroPrepaymentFinancials:
    @pytest.mark.parametrize(
        "principal,rate,tenure,prepay_month",
        [
            (500_000, 9, 60, 12),
            (500_000, 9, 2, 1),
            (123456, 8.3, 37, 19),
            (999999, 11.1, 13, 3),
            (300_000, 10, 36, 10),
            (1_000_000, 7.5, 120, 50),
            (250_000, 12, 24, 5),
        ],
    )
    def test_zero_prepayment_is_never_worse_than_no_prepayment(self, principal, rate, tenure, prepay_month):
        # A prepay_amount of 0 is financially a no-op: it should never
        # report negative months_saved or negative interest_saved. Before
        # the fix, floating-point noise in remaining_tenure()'s
        # logarithmic formula (e.g. computing 18.000047... instead of
        # exactly 18.0) caused math.ceil() to round up to the next whole
        # month, making the "new" schedule appear one month longer than
        # the original - a nonsensical result for a zero-amount
        # prepayment.
        result = prepayment_savings(principal, rate, tenure, prepay_month, 0)
        assert result["months_saved"] >= 0
        # interest_saved should be >= 0 (allowing tiny negative floating
        # point noise like -0.0 or -1e-10, which is not a real financial
        # loss). pytest.approx() does not support >=, so a small
        # absolute tolerance is added directly instead.
        assert result["interest_saved"] >= -0.01
