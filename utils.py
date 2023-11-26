import datetime
import dateutil.relativedelta


def first_day_of_the_month(relative_months: int = 0) -> datetime.datetime:
    """Return the first day of the month as a datetime"""
    first_day_of_this_month = datetime.datetime.today().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_day_of_this_month + dateutil.relativedelta.relativedelta(months=relative_months)


def last_day_of_the_month() -> datetime:
    """Return the last day of the month as a datetime"""
    # The day 28 exists in every month. 4 days later, it's always next month
    next_month = datetime.datetime.today().replace(day=28) + datetime.timedelta(days=4)

    return next_month - datetime.timedelta(days=next_month.day)