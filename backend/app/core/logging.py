import logging
import re

import structlog

_TOKEN_RE = re.compile(r"(token=)[^&\s]+")


def scrub_sensitive(logger, method_name, event_dict):
    for key in ("password", "new_password", "token", "access_token", "refresh_token"):
        if key in event_dict:
            event_dict[key] = "***"
    if "phone" in event_dict and isinstance(event_dict["phone"], str):
        p = event_dict["phone"]
        event_dict["phone"] = "***" + p[-4:] if len(p) >= 4 else "***"
    for k in ("lat", "lng"):
        if isinstance(event_dict.get(k), (int, float)):
            event_dict[k] = round(event_dict[k], 2)
    if isinstance(event_dict.get("email"), str) and "@" in event_dict["email"]:
        event_dict["email"] = "***@" + event_dict["email"].split("@", 1)[1]
    if isinstance(event_dict.get("url"), str):
        event_dict["url"] = _TOKEN_RE.sub(r"\1***", event_dict["url"])
    return event_dict


class _HealthCheckFilter(logging.Filter):
    """Drop uvicorn access-log records for the /health endpoint.

    The container HEALTHCHECK polls /health every ~10s; logging each hit
    floods the logs with no diagnostic value.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


def configure_logging(level: str = "DEBUG") -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            scrub_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )

    # APScheduler emits an INFO line per tick ("Looking for jobs", "Next wakeup",
    # "Running job ... executed successfully") — far too chatty. Surface only warnings.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    # Suppress uvicorn access-log spam from the every-10s container healthcheck.
    logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())
