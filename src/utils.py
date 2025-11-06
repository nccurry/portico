import datetime
import dateutil.relativedelta


def first_day_of_month(
        relative_months: int = 0
) -> datetime.datetime:
    """Return the first day of the month as a datetime"""
    first_day_of_this_month = datetime.datetime.today().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return first_day_of_this_month + dateutil.relativedelta.relativedelta(months=relative_months)


def last_day_of_month(
        relative_months: int = 0
) -> datetime.datetime:
    """Return the last day of the month as a datetime"""
    first_day_of_the_relative_month = first_day_of_month(relative_months=relative_months)
    # The day 28 exists in every month. 4 days later, it's always next month
    next_month = first_day_of_the_relative_month.replace(day=28) + datetime.timedelta(days=4)

    return next_month - datetime.timedelta(days=next_month.day)


def this_day_of_month(
        relative_months: int = 0
) -> datetime.datetime:
    """Return the same day of a relative month as a datetime"""
    today = datetime.datetime.today()

    return first_day_of_month(relative_months=relative_months).replace(day=today.day)




def relative_date(
        relative_days: int = 30
) -> datetime.datetime:
    """Return the date relative_days from now as a datetime"""
    start_of_today = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    return start_of_today + datetime.timedelta(days=relative_days)


def format_dollar_amount(
        dollar_amount: float
) -> str:
    """Format a float as a dollar amount to include dollar, two decimal places, and negative sign"""
    sign = "-" if dollar_amount < 0 else ""

    return sign + "${:,.2f}".format(abs(dollar_amount))


# Common periods to use when calculating spending
SPENDING_PERIODS = {
    "Last 7 Days": {
        "start_date": relative_date(-7),
        "end_date": relative_date(-1),
        "start_date_previous": relative_date(-14),
        "end_date_previous": relative_date(-8),
    },
    "Last 14 Days": {
        "start_date": relative_date(-14),
        "end_date": relative_date(-1),
        "start_date_previous": relative_date(-28),
        "end_date_previous": relative_date(-15),
    },
    "Last 28 Days": {
        "start_date": relative_date(-28),
        "end_date": relative_date(-1),
        "start_date_previous": relative_date(-56),
        "end_date_previous": relative_date(-29),
    },
    "This Month": {
        "start_date": first_day_of_month(relative_months=0),
        "end_date": relative_date(relative_days=0),
        "start_date_previous": first_day_of_month(relative_months=-1),
        "end_date_previous": this_day_of_month(relative_months=-1),
    },
    "Last Month": {
        "start_date": first_day_of_month(relative_months=-1),
        "end_date": last_day_of_month(relative_months=-1),
        "start_date_previous": first_day_of_month(relative_months=-2),
        "end_date_previous": last_day_of_month(relative_months=-2),
    },
    "Last 3 Months": {
        "start_date": first_day_of_month(relative_months=-3),
        "end_date": last_day_of_month(relative_months=-1),
        "start_date_previous": first_day_of_month(relative_months=-6),
        "end_date_previous": last_day_of_month(relative_months=-4),
    },
    "Last 6 Months": {
        "start_date": first_day_of_month(relative_months=-6),
        "end_date": last_day_of_month(relative_months=-1),
        "start_date_previous": first_day_of_month(relative_months=-12),
        "end_date_previous": last_day_of_month(relative_months=-7),
    },
    "Last 12 Months": {
        "start_date": first_day_of_month(relative_months=-12),
        "end_date": last_day_of_month(relative_months=-1),
        "start_date_previous": first_day_of_month(relative_months=-24),
        "end_date_previous": last_day_of_month(relative_months=-13),
    },
}
