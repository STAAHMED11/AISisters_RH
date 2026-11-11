from datetime import UTC, datetime

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def format_date(dt: datetime | None, lang: str = "fr") -> str:
    if not dt:
        return ""
    d = aware(dt)
    return f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}" if lang == "en" else f"{d.day} {MONTHS_FR[d.month - 1]} {d.year}"
