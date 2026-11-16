class DomainError(Exception):
    """Error from the application domain, independent of HTTP."""


class EventNotFound(DomainError):
    pass


class EventNotPublished(DomainError):
    pass


class RegistrationClosed(DomainError):
    pass


class SeatUnavailable(DomainError):
    pass


class TicketNotFound(DomainError):
    pass


class EventAlreadyStarted(DomainError):
    pass


class ProviderResourceNotFound(DomainError):
    pass


class ProviderRejected(DomainError):
    pass


class ProviderAuthenticationFailed(DomainError):
    pass


class ProviderRateLimited(DomainError):
    pass


class ProviderUnavailable(DomainError):
    pass
