from apps.admin_panel.domain.errors import AdminPanelDomainError


class AdminPanelApplicationError(AdminPanelDomainError):
    """Application-layer admin error with an HTTP-oriented contract."""

    default_code = "admin_panel_error"


class TrainingApplicationError(AdminPanelApplicationError):
    """Training-specific application error contract."""

    default_code = "training_error"
