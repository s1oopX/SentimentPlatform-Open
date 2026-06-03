class AdminPanelDomainError(ValueError):
    """Thin shared error substrate for controlled admin/domain failures."""

    default_code = "admin_panel_error"

    def __init__(self, code, message=None, *, status_code=400):
        if isinstance(message, int):
            status_code = message
            message = str(code)
            code = self.default_code
        elif message is None:
            message = str(code)
            code = self.default_code

        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
