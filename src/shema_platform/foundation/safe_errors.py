from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

_MAX_ERROR_CHARS = 1024

_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)(basic\s+)([^\s,;]+)"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s+)([^\s,;]+)"),
    re.compile(r"(?i)(api[-_ ]?key\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(client_secret\s*[:=]\s*)([^\s,;]+)"),
)


def safe_error_detail(error: BaseException | str, *, max_chars: int = _MAX_ERROR_CHARS) -> str:
    """Return a bounded, credential-redacted error string for durable telemetry/audit."""

    if max_chars < 64:
        raise ValueError("max_chars must be >= 64")

    value = str(error).replace("\x00", "")
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(r"\1<redacted>", value)

    # Redact credentials embedded in URLs while preserving the host/path.
    def redact_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        try:
            parsed = urlsplit(raw)
            if parsed.username is None and parsed.password is None:
                return raw
            hostname = parsed.hostname or ""
            netloc = hostname
            if parsed.port is not None:
                netloc = f"{netloc}:{parsed.port}"
            return urlunsplit(
                (
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                )
            )
        except ValueError:
            return "<redacted-url>"

    value = re.sub(r"https?://[^\s]+", redact_url, value)
    value = " ".join(value.split())
    if len(value) > max_chars:
        return value[: max_chars - 3] + "..."
    return value
