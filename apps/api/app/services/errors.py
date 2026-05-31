class ServiceError(Exception):
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = 404


class BadRequestError(ServiceError):
    status_code = 400


class InvalidTraceState(ServiceError):
    status_code = 409
