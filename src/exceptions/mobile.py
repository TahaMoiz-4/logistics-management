"""src/exceptions/mobile.py — mobile-app HTTPExceptions."""

from src.exceptions.common import AppException


class NotAssignedToYou(AppException):
    def __init__(self):
        super().__init__(403, "not_assigned_to_you",
                         "This job is not assigned to you.")


class StopNotFound(AppException):
    def __init__(self, stop_id: int):
        super().__init__(404, "stop_not_found",
                         f"Assignment stop {stop_id} was not found.")


class StopAlreadyCompleted(AppException):
    def __init__(self):
        super().__init__(409, "stop_already_completed",
                         "This job is already completed.")


class WorkerHasNoRole(AppException):
    def __init__(self):
        super().__init__(409, "worker_has_no_role",
                         "Your account is not linked to a nurse, technician, or driver record.")


class InvalidStopStatus(AppException):
    def __init__(self, status: str):
        super().__init__(400, "invalid_stop_status",
                         f"'{status}' is not a valid job status update.")
