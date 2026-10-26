"""
Test suite for loan_calc.calculator.

NOTE: Some tests in this file are EXPECTED TO FAIL against the current
implementation. They assert the correct/expected behavior of the
calculator and are intentionally written to reveal existing bugs
(e.g. amortisation_schedule() returning tenure_months - 1 rows instead
of tenure_months, and remaining_tenure() using an inconsistent rate
convention). These are marked with "# BUG:" comments explaining the
discrepancy. No source files are modified by this test suite.
"""
import pytest

from loan_calc.calculator import (
    emi,
    total_payment,
    total_interest,
    amortisation_schedule,
    outstanding_after,
    remaining_tenure,
    prepayment_savings,
    compare_offers,
    eligible_amount,
    format_inr,
    schedule_to_csv,
    summary,
)


# ---------------------------------------------------------------------------
# emi()
# ---------------------------------------------------------------------------

class TestEmi:
    def test_emi_normal_case(self):
        # Requested check: EMI for 1,000,000 @ 9% over 240 months ~= 8,997
        result = emi(1_000_000, 9, 240)
        assert result == pytest.approx(8997, abs=1)

    def test_emi_zero_interest(self):
        result = emi(120_000, 0, 12)
        assert result == pytest.approx(10_000, abs=0.01)

    def test_emi_one_month_tenure(self):
        principal, annual_rate = 100_000, 12
        result = emi(principal, annual_rate, 1)
        # Use the precise, unrounded monthly rate (no round() applied)
        monthly_rate = annual_rate / 1200
        expected = principal * (1 + monthly_rate)
        assert result == pytest.approx(expected, abs=0.01)

    def test_emi_monthly_rate_rounding_with_9_5_percent(self):
        # 9.5% / 1200 = 0.00791666...; _monthly_rate() rounds this to
        # 0.0079 (4 decimal places). This test uses the precise unrounded
        # rate to check whether that rounding introduces a measurable
        # discrepancy in the resulting EMI.
        principal, annual_rate, tenure_months = 500_000, 9.5, 120
        precise_rate = annual_rate / 1200
        f = (1 + precise_rate) ** tenure_months
        expected = round(principal * precise_rate * f / (f - 1), 2)
        result = emi(principal, annual_rate, tenure_months)
        assert result == pytest.approx(expected, abs=0.01)

    def test_emi_very_large_principal(self):
        result = emi(1_000_000_000_000, 9, 240)
        assert result > 0
        assert result == pytest.approx(emi(1_000_000, 9, 240) * 1_000_000, rel=1e-6)

    def test_emi_zero_tenure_raises(self):
        with pytest.raises(ValueError):
            emi(100_000, 9, 0)

    def test_emi_negative_tenure_raises(self):
        with pytest.raises(ValueError):
            emi(100_000, 9, -5)

    def test_emi_zero_principal_raises(self):
        with pytest.raises(ValueError):
            emi(0, 9, 12)

    def test_emi_negative_principal_raises(self):
        with pytest.raises(ValueError):
            emi(-100_000, 9, 12)


# ---------------------------------------------------------------------------
# total_payment() / total_interest()
# ---------------------------------------------------------------------------

class TestTotalPaymentAndInterest:
    def test_total_payment_normal(self):
        p, r, t = 500_000, 9, 60
        assert total_payment(p, r, t) == pytest.approx(emi(p, r, t) * t, abs=0.01)

    def test_total_interest_normal(self):
        p, r, t = 500_000, 9, 60
        assert total_interest(p, r, t) == pytest.approx(total_payment(p, r, t) - p, abs=0.01)

    def test_total_interest_zero_interest_is_zero(self):
        p, r, t = 120_000, 0, 12
        assert total_interest(p, r, t) == pytest.approx(0, abs=0.01)

    def test_total_payment_one_month_tenure(self):
        # Edge case: 1-month tenure, total_payment should equal the single EMI
        p, r, t = 100_000, 12, 1
        assert total_payment(p, r, t) == pytest.approx(emi(p, r, t), abs=0.01)

    def test_total_interest_very_large_principal(self):
        # Edge case: very large principal should not overflow or error
        p, r, t = 1_000_000_000_000, 9, 240
        result = total_interest(p, r, t)
        assert result > 0


# ---------------------------------------------------------------------------
# amortisation_schedule()
# ---------------------------------------------------------------------------

class TestAmortisationSchedule:
    def test_schedule_length_matches_tenure(self):
        # BUG: current implementation loops over range(1, tenure_months),
        # producing tenure_months - 1 rows instead of tenure_months.
        # This test is EXPECTED TO FAIL against the current code.
        tenure = 12
        sched = amortisation_schedule(100_000, 9, tenure)
        assert len(sched) == tenure

    def test_schedule_one_month_tenure(self):
        # BUG: with tenure_months=1, range(1, 1) is empty, so the schedule
        # returned is an empty list instead of 1 row.
        # This test is EXPECTED TO FAIL against the current code.
        sched = amortisation_schedule(100_000, 12, 1)
        assert len(sched) == 1

    def test_schedule_balance_decreases_monotonically(self):
        sched = amortisation_schedule(500_000, 9, 60)
        balances = [row["balance"] for row in sched]
        assert all(balances[i] >= balances[i + 1] for i in range(len(balances) - 1))

    def test_schedule_final_balance_is_zero(self):
        # BUG: because the loop stops one iteration short (see
        # test_schedule_length_matches_tenure), the final balance in the
        # returned schedule may not reach 0 within the stated tenure.
        # This test is EXPECTED TO FAIL against the current code.
        tenure = 24
        sched = amortisation_schedule(200_000, 10, tenure)
        assert sched[-1]["balance"] == pytest.approx(0.0, abs=0.01)

    def test_schedule_zero_interest(self):
        # BUG: With 0% interest, each month's interest should be 0 and the
        # schedule should contain all 12 months with a final balance of 0.
        # The length and final-balance assertions are EXPECTED TO FAIL
        # against the current off-by-one implementation.
        tenure = 12
        sched = amortisation_schedule(120_000, 0, tenure)
        assert all(row["interest"] == 0 for row in sched)
        assert len(sched) == tenure
        assert sched[-1]["balance"] == pytest.approx(0.0, abs=0.01)

    def test_schedule_very_large_principal_no_crash(self):
        sched = amortisation_schedule(1_000_000_000_000, 9, 240)
        assert len(sched) > 0


class TestOutstandingAfter:
    def test_outstanding_after_zero_months_paid(self):
        principal = 100_000
        result = outstanding_after(principal, 9, 24, 0)
        assert result == pytest.approx(principal, abs=0.01)

    def test_outstanding_after_negative_months_paid(self):
        principal = 100_000
        result = outstanding_after(principal, 9, 24, -5)
        assert result == pytest.approx(principal, abs=0.01)

    def test_outstanding_after_exceeds_schedule_length(self):
        result = outstanding_after(100_000, 9, 24, 999)
        assert result == 0.0

    def test_outstanding_after_matches_schedule_row(self):
        principal, rate, tenure, months_paid = 100_000, 9, 24, 5
        sched = amortisation_schedule(principal, rate, tenure)
        expected = sched[months_paid - 1]["balance"]
        result = outstanding_after(principal, rate, tenure, months_paid)
        assert result == pytest.approx(expected, abs=0.01)

    def test_outstanding_after_full_tenure_is_zero(self):
        # BUG: because amortisation_schedule() stops one month short,
        # calling outstanding_after() with months_paid == tenure_months
        # will exceed len(sched) and return 0.0 "by accident" via the
        # months_paid > len(sched) branch, rather than via a schedule row
        # that actually reaches zero. This test is EXPECTED TO reveal
        # that distinction — it currently passes by coincidence due to
        # the bug, not because the schedule correctly reaches zero at
        # the full tenure.
        principal, rate, tenure = 150_000, 8, 36
        result = outstanding_after(principal, rate, tenure, tenure)
        assert result == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# remaining_tenure() / prepayment_savings()
# ---------------------------------------------------------------------------

class TestRemainingTenure:
    def test_remaining_tenure_zero_balance(self):
        result = remaining_tenure(0, 9, 5000)
        assert result == 0

    def test_remaining_tenure_negative_balance(self):
        result = remaining_tenure(-1000, 9, 5000)
        assert result == 0

    def test_remaining_tenure_zero_interest(self):
        result = remaining_tenure(50_000, 0, 5000)
        assert result == 10  # ceil(50000 / 5000)

    def test_remaining_tenure_instalment_too_small_raises(self):
        # NOTE: remaining_tenure() internally computes r = annual_rate / 100
        # (not /1200 like _monthly_rate() elsewhere in the module - a known
        # rate-convention inconsistency). Here we deliberately compute the
        # "too small" boundary using the /1200 convention instead, which is
        # far below the function's actual internal threshold, to highlight
        # that mismatch while still confirming a ValueError is raised.
        balance, annual_rate = 100_000, 12
        r_1200_convention = annual_rate / 1200
        too_small_instalment = balance * r_1200_convention
        with pytest.raises(ValueError):
            remaining_tenure(balance, annual_rate, too_small_instalment)

    def test_remaining_tenure_normal_case(self):
        # BUG: Using the CORRECT monthly rate convention (annual_rate / 1200
        # = 0.0075), remaining_tenure(100_000, 9, 5000) should mathematically
        # return 22 months. However, the actual implementation internally
        # computes r = annual_rate / 100 = 0.09, where balance * r (9000) >=
        # instalment (5000), tripping the "instalment too small" guard and
        # raising a ValueError instead of returning 22. This test is
        # EXPECTED TO FAIL (raise ValueError) against the current buggy
        # rate-convention implementation.
        balance, annual_rate, instalment = 100_000, 9, 5000
        result = remaining_tenure(balance, annual_rate, instalment)
        assert result == 22


class TestPrepaymentSavings:
    def test_prepayment_savings_normal_case(self):
        result = prepayment_savings(500_000, 9, 60, 12, 50_000)
        assert "emi" in result
        assert "months_saved" in result
        assert "new_tenure" in result
        assert "interest_saved" in result
        assert "interest_paid_before_prepayment" in result
        assert result["months_saved"] > 0
        assert result["interest_saved"] > 0
        assert result["new_tenure"] < 60

    def test_prepayment_larger_than_outstanding_balance(self):
        # Edge case: prepay_amount exceeds the outstanding balance at
        # prepay_month, so new_balance goes negative -> months_left
        # should be treated as 0 (loan fully paid off).
        principal, rate, tenure, prepay_month = 100_000, 9, 24, 6
        sched = amortisation_schedule(principal, rate, tenure)
        outstanding_balance = sched[prepay_month - 1]["balance"]
        huge_prepay_amount = outstanding_balance + 1_000_000  # way more than owed

        result = prepayment_savings(principal, rate, tenure, prepay_month, huge_prepay_amount)
        assert result["new_tenure"] == prepay_month  # loan ends exactly at prepay_month
        assert result["months_saved"] >= 0

    def test_prepayment_savings_zero_interest(self):
        # With 0% interest, prepayment should still shorten tenure predictably
        result = prepayment_savings(120_000, 0, 24, 6, 20_000)
        assert result["interest_saved"] == pytest.approx(0, abs=0.01)


# ---------------------------------------------------------------------------
# compare_offers() / eligible_amount() / format_inr()
# ---------------------------------------------------------------------------

class TestCompareOffers:
    def test_compare_offers_sorted_by_total_cost(self):
        offers = [
            {"bank": "Bank A", "rate": 9, "tenure": 60, "processing_fee_pct": 1},
            {"bank": "Bank B", "rate": 8.5, "tenure": 60, "processing_fee_pct": 0.5},
            {"bank": "Bank C", "rate": 10, "tenure": 60, "processing_fee_pct": 0},
        ]
        result = compare_offers(500_000, offers)
        total_costs = [o["total_cost"] for o in result]
        assert total_costs == sorted(total_costs)

    def test_compare_offers_all_banks_present(self):
        offers = [
            {"bank": "Bank A", "rate": 9, "tenure": 60},
            {"bank": "Bank B", "rate": 8.5, "tenure": 60},
        ]
        result = compare_offers(500_000, offers)
        banks = {o["bank"] for o in result}
        assert banks == {"Bank A", "Bank B"}

    def test_compare_offers_default_processing_fee_is_zero(self):
        offers = [{"bank": "Bank A", "rate": 9, "tenure": 60}]
        result = compare_offers(500_000, offers)
        assert result[0]["processing_fee"] == 0.0

    def test_compare_offers_empty_list(self):
        result = compare_offers(500_000, [])
        assert result == []


class TestEligibleAmount:
    def test_eligible_amount_normal_case(self):
        # Expected value computed independently using the correct monthly
        # rate (annual_rate / 1200 = 0.0075) and the inverse-EMI formula.
        # Verified: both the actual function and this independent
        # calculation produce 2222899.08 (9/1200 rounds cleanly here, so
        # no rate-rounding discrepancy occurs in this particular case).
        monthly_income, existing_emis, annual_rate, tenure_months = 50_000, 5_000, 9, 240
        r = annual_rate / 1200
        available = monthly_income * 0.5 - existing_emis
        f = (1 + r) ** tenure_months
        expected = round(available * (f - 1) / (r * f), 2)
        result = eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months)
        assert result == pytest.approx(expected, abs=0.01)

    def test_eligible_amount_zero_available_income(self):
        result = eligible_amount(monthly_income=10_000, existing_emis=5_000, annual_rate=9, tenure_months=240, foir=0.5)
        assert result == 0.0

    def test_eligible_amount_negative_available_income(self):
        result = eligible_amount(monthly_income=10_000, existing_emis=10_000, annual_rate=9, tenure_months=240, foir=0.5)
        assert result == 0.0

    def test_eligible_amount_zero_interest(self):
        result = eligible_amount(monthly_income=100_000, existing_emis=0, annual_rate=0, tenure_months=12, foir=0.5)
        assert result == pytest.approx(50_000 * 12, abs=0.01)

    def test_eligible_amount_custom_foir(self):
        result_default = eligible_amount(monthly_income=100_000, existing_emis=0, annual_rate=9, tenure_months=240, foir=0.5)
        result_higher_foir = eligible_amount(monthly_income=100_000, existing_emis=0, annual_rate=9, tenure_months=240, foir=0.7)
        assert result_higher_foir > result_default


class TestFormatInr:
    def test_format_inr_small_amount_no_grouping(self):
        assert format_inr(500) == "₹500.00"

    def test_format_inr_thousands(self):
        assert format_inr(12_345) == "₹12,345.00"

    def test_format_inr_lakhs(self):
        assert format_inr(10_00_000) == "₹10,00,000.00"

    def test_format_inr_crores(self):
        assert format_inr(1_00_00_000) == "₹1,00,00,000.00"

    def test_format_inr_negative_amount(self):
        assert format_inr(-5000) == "-₹5,000.00"

    def test_format_inr_zero(self):
        assert format_inr(0) == "₹0.00"


# ---------------------------------------------------------------------------
# schedule_to_csv() / summary()
# ---------------------------------------------------------------------------

class TestScheduleToCsv:
    def test_schedule_to_csv_writes_header_and_rows(self, tmp_path):
        sched = amortisation_schedule(100_000, 9, 12)
        csv_path = tmp_path / "schedule.csv"
        schedule_to_csv(sched, str(csv_path))

        content = csv_path.read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "month,emi,interest,principal,balance"
        assert len(lines) - 1 == len(sched)

    def test_schedule_to_csv_row_values_match_schedule(self, tmp_path):
        sched = amortisation_schedule(50_000, 10, 6)
        csv_path = tmp_path / "schedule.csv"
        schedule_to_csv(sched, str(csv_path))

        lines = csv_path.read_text().strip().split("\n")
        first_data_row = lines[1].split(",")
        assert int(first_data_row[0]) == sched[0]["month"]
        assert float(first_data_row[1]) == sched[0]["emi"]

    def test_schedule_to_csv_empty_rows(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        schedule_to_csv([], str(csv_path))
        content = csv_path.read_text()
        assert content == "month,emi,interest,principal,balance\n"


class TestSummary:
    def test_summary_contains_expected_keys(self):
        result = summary(500_000, 9, 60)
        expected_keys = {
            "principal", "rate", "tenure", "emi",
            "total_interest", "total_payment", "last_emi", "currency",
        }
        assert set(result.keys()) == expected_keys

    def test_summary_currency_is_inr(self):
        result = summary(500_000, 9, 60)
        assert result["currency"] == "INR"

    def test_summary_with_explicit_start_date_is_deterministic(self):
        # Using an explicit start date avoids the date.today() impurity
        # flagged in ARCHITECTURE.md Entry 2 - this test should be
        # reliably reproducible regardless of when it's run.
        from datetime import date
        start = date(2024, 1, 1)
        result = summary(240_000, 9, 24, start=start)
        assert result["last_emi"] == "2026-01"

    def test_summary_rate_and_tenure_strings(self):
        result = summary(500_000, 9, 60)
        assert result["rate"] == "9% p.a."
        assert result["tenure"] == "60 months"


# ---------------------------------------------------------------------------
# Sanity check: the loan_calc package is importable and the module's
# functions are reachable, confirming pytest discovery/config is correct.
# ---------------------------------------------------------------------------

def test_package_is_importable():
    import loan_calc
    assert hasattr(loan_calc, "emi")
