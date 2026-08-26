from __future__ import annotations

from .context import PaymentContext
from .errors import PaymentValidationError


def validate_payment_context(context: PaymentContext) -> PaymentContext:
    if not isinstance(context.amount_paise, int) or isinstance(context.amount_paise, bool):
        raise PaymentValidationError("amount must be integer paise")
    if context.amount_paise <= 0:
        raise PaymentValidationError("amount must be positive")
    if context.currency != "INR":
        raise PaymentValidationError("unsupported currency")
    return context


def validate_provider_amount_currency(amount_paise: int, currency: str, expected_amount_paise: int, expected_currency: str) -> None:
    if type(amount_paise) is not int or amount_paise != expected_amount_paise:
        raise PaymentValidationError("provider amount does not match stored amount")
    if currency != expected_currency:
        raise PaymentValidationError("provider currency does not match stored currency")
