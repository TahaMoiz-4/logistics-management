"""src/exceptions/route_plans.py — RoutePlan lifecycle HTTPExceptions."""

from src.exceptions.common import AppException


class PlanNotReady(AppException):
    def __init__(self, status: str):
        super().__init__(409, "plan_not_ready",
                         f"This plan is '{status}' — only a 'ready' plan can be approved.")


class PlanAlreadyDispatched(AppException):
    def __init__(self):
        super().__init__(409, "plan_already_dispatched",
                         "This plan has already been approved and dispatched.")


class PlanNotDeletable(AppException):
    def __init__(self, status: str):
        super().__init__(409, "plan_not_deletable",
                         f"A '{status}' plan cannot be deleted; only draft/ready/failed plans can.")


class NoDiagnostics(AppException):
    def __init__(self, status: str):
        super().__init__(409, "no_diagnostics",
                         f"This plan has no solver diagnostics yet (status='{status}').")
