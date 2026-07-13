"""
src/exceptions/orders.py

Order + order-selection HTTPExceptions. See common.AppException for the shape.
"""

from src.exceptions.common import AppException


class OrdersNotFound(AppException):
    def __init__(self, ids):
        super().__init__(400, "orders_not_found",
                         f"These orders do not exist: {list(ids)}.")


class OrdersNotOwned(AppException):
    def __init__(self, ids):
        super().__init__(400, "orders_not_owned",
                         f"These orders belong to another company: {list(ids)}.")


class OrdersNotServable(AppException):
    def __init__(self, ids):
        super().__init__(400, "orders_not_servable",
                         f"These orders are not servable (must be pending or assigned): {list(ids)}.")


class OrdersMissingServiceDate(AppException):
    def __init__(self, ids):
        super().__init__(400, "orders_missing_service_date",
                         f"These orders have no service_date set: {list(ids)}.")


class OrdersSpanMultipleDates(AppException):
    def __init__(self, dates):
        super().__init__(400, "orders_span_multiple_dates",
                         f"Selected orders span multiple service dates {sorted(str(d) for d in dates)}; "
                         f"a route plan solves exactly one day — create one plan per date.")


class PlannedDateMismatch(AppException):
    def __init__(self, planned_date, derived):
        super().__init__(400, "planned_date_mismatch",
                         f"planned_date {planned_date} does not match the selected orders' "
                         f"service_date {derived}.")


class SelectionMissing(AppException):
    def __init__(self):
        super().__init__(400, "selection_missing",
                         "Provide either order_ids or planned_date.")


class NoServableOrders(AppException):
    def __init__(self, company_id, planned_date):
        super().__init__(400, "no_servable_orders",
                         f"No servable orders for company {company_id} on {planned_date}.")
