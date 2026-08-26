from backend.app.domain import DomainError


class PaymentError(DomainError):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class PaymentAuthorityError(PaymentError):
    pass


class PaymentValidationError(PaymentError):
    pass


class PaymentProviderError(PaymentError):
    def __init__(self, code: str = "provider_failure") -> None:
        self.code = code
        super().__init__(code)


class PaymentWebhookError(PaymentError):
    pass
