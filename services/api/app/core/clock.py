"""The mill works in Indian Standard Time; dates on bills and deadlines are IST dates, whatever the server's own zone is."""
import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> dt.date:
    return dt.datetime.now(IST).date()
