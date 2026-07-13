"""
src/exceptions/auth.py

Auth-related HTTPExceptions. See common.AppException for the detail shape.
"""

from src.exceptions.common import AppException


class InvalidCredentials(AppException):
    def __init__(self):
        super().__init__(401, "invalid_credentials",
                         "The username or password is incorrect.")


class InvalidToken(AppException):
    def __init__(self):
        super().__init__(401, "invalid_token",
                         "Your session is invalid or has expired. Please log in again.")


class InactiveAccount(AppException):
    def __init__(self):
        super().__init__(403, "inactive_account",
                         "This account is inactive. Contact your administrator.")


class NotAuthenticated(AppException):
    def __init__(self):
        super().__init__(401, "not_authenticated",
                         "Authentication is required for this action.")
