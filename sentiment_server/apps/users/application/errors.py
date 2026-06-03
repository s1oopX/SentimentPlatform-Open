class UserApplicationError(Exception):
    def __init__(self, message, status_code, *, code="user_application_error"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class UserServiceError(UserApplicationError):
    def __init__(self, message, status_code, *, code="user_service_error"):
        super().__init__(message, status_code, code=code)
