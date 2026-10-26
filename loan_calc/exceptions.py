"""
Custom exception hierarchy for loan_calc input validation.

All exceptions inherit from LoanCalculatorError, which itself inherits
from the built-in ValueError. This ensures backward compatibility: any
existing code or tests that catch ValueError (or use
pytest.raises(ValueError)) will continue to work unchanged, since every
custom exception here *is a* ValueError.
"""


class LoanCalculatorError(ValueError):
    """
    Base exception for all loan_calc input-validation errors.

    Inherits from ValueError so existing code/tests that catch
    ValueError continue to work without modification.
    """
    pass


class InvalidPrincipalError(LoanCalculatorError):
    """Raised when a loan principal is not a positive number, or is not
    a valid numeric type (e.g. wrong type, NaN, or infinite)."""
    pass


class InvalidRateError(LoanCalculatorError):
    """Raised when an annual interest rate is negative, or is not a
    valid numeric type (e.g. wrong type, NaN, or infinite)."""
    pass


class InvalidTenureError(LoanCalculatorError):
    """Raised when a loan tenure (in months) is not a positive integer,
    or is not a valid integer-like type."""
    pass


class InvalidInstalmentError(LoanCalculatorError):
    """Raised when an instalment/EMI amount is not a positive number,
    is too small to ever repay the outstanding balance, or is not a
    valid numeric type (e.g. wrong type, NaN, or infinite)."""
    pass


class InvalidPrepaymentError(LoanCalculatorError):
    """Raised when prepayment parameters (month or amount) are invalid,
    including wrong type, out-of-range month, negative amount, or
    non-finite numeric values."""
    pass


class InvalidIncomeError(LoanCalculatorError):
    """Raised when income/FOIR parameters for eligibility calculation
    are invalid, including wrong type, non-positive income, negative
    existing EMIs, out-of-range FOIR, or non-finite numeric values."""
    pass
