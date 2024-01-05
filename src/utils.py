import datetime
import dateutil.relativedelta


def first_day_of_month(relative_months: int = 0) -> datetime.datetime:
    """Return the first day of the month as a datetime"""
    first_day_of_this_month = datetime.datetime.today().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return first_day_of_this_month + dateutil.relativedelta.relativedelta(months=relative_months)


def last_day_of_month(relative_months: int = 0) -> datetime:
    """Return the last day of the month as a datetime"""
    first_day_of_the_relative_month = first_day_of_month(relative_months=relative_months)
    # The day 28 exists in every month. 4 days later, it's always next month
    next_month = first_day_of_the_relative_month.replace(day=28) + datetime.timedelta(days=4)

    return next_month - datetime.timedelta(days=next_month.day)


def relative_date(relative_days: int = 30) -> datetime:
    """Return the date relative_days from now as a datetime"""
    start_of_today = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    return start_of_today + datetime.timedelta(days=relative_days)


def format_dollar_amount(dollar_amount: float) -> str:
    """Format a float as a dollar amount to include dollar, two decimal places, and negative sign"""
    sign = "-" if dollar_amount < 0 else ""

    return sign + "${:,.2f}".format(abs(dollar_amount))
