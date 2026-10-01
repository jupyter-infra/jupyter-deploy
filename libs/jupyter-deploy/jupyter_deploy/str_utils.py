from datetime import UTC, datetime

from pydantic import ValidationError


def to_cli_option_name(s: str) -> str:
    """Return name to kebab-case CLI option format.

    Examples:
        FullTitleCase -> full-title-case
        camelCaseName -> camel-case-name
        python_var_name -> python-var-name
        SomeMixed-Case -> some-mixed-case
    """
    if not s:
        return s

    result = []
    prev_char = s[0]
    result.append(prev_char.lower())

    for curr_char in s[1:]:
        # Handle camelCase and TitleCase
        if curr_char.isupper() and prev_char.islower():
            result.append("-")
            result.append(curr_char.lower())
        # Handle underscores
        elif curr_char == "_":
            if prev_char != "-" and prev_char != "_":
                result.append("-")
        # Handle existing hyphens
        elif curr_char == "-":
            if prev_char != "-":
                result.append("-")
        else:
            result.append(curr_char.lower())

        prev_char = curr_char

    return "".join(result).strip("-")


def get_trimmed_header(full_text: str, max_length: int = 120) -> str:
    """Return the full line of text, up to the char limit."""
    if not full_text or max_length <= 0:
        return ""

    no_leading_white_spaces_text = full_text.lstrip()
    trimmed_text = no_leading_white_spaces_text[:max_length]

    split_trimmed_text = trimmed_text.split("\n")
    return split_trimmed_text[0]


def to_list_str(concatenated_list: str, sep: str = ",") -> list[str]:
    """Split the string by the separator, return result."""
    if not concatenated_list:
        return []

    items = concatenated_list.split(sep)
    return items


def describe_validation_errors(error: ValidationError, root_field: str | None = None) -> list[str]:
    """Return one user-facing line per pydantic error, each pointing at the offending part of the value.

    Pydantic's own rendering names the model class, repeats the whole input, and appends a docs URL:
    noise for a user who passed the value in a yaml file and has no model to look at. This keeps the
    part they can act on -- the reason, and where in their value it applies.

    Args:
        error: The pydantic error to describe.
        root_field: Model field the value was validated under, dropped from each path when present,
            so paths read from the user's value rather than from the model wrapping it.

    Examples:
        Input should be a valid list, got: str
        at [1].disk_size_gb: Input should be a valid string, got: int
    """
    lines: list[str] = []

    for err in error.errors():
        loc = err["loc"]
        if root_field and loc[:1] == (root_field,):
            loc = loc[1:]
        path = "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in loc).lstrip(".")
        location = f"at {path}: " if path else ""
        lines.append(f"{location}{err['msg']}, got: {type(err['input']).__name__}")
    return lines


def parse_timestamp(raw: str) -> datetime | None:
    """Parse an ISO-8601 timestamp to an aware datetime, or None when it is absent or unparseable.

    Naive input is read as UTC: every producer here is a cloud API reporting an instant in UTC, and an
    aware value is what callers need to compare against another timestamp without raising.

    None rather than a raise, because "no usable timestamp" is a normal answer from an API that reports
    a field only sometimes -- and callers that must not guess (a data-safety check) can treat None as a
    refusal, while callers that only display it can fall back to the raw string.
    """
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def format_timestamp(raw: str) -> str:
    """Format an ISO timestamp to a human-readable UTC date string."""
    parsed = parse_timestamp(raw)
    if parsed is None:
        return raw
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def format_age(iso_timestamp: str) -> str:
    """Convert an ISO timestamp to a human-readable age (e.g. '3h ago', '2d ago').

    Unit switches by magnitude so the value stays short in a table cell or a one-line status.
    An empty input yields "", and an unparseable one is returned verbatim rather than guessed at —
    a caller rendering a table would rather show the raw value than a wrong age.

    Lived in `api/k8s/utils.py` until it acquired a second caller outside Kubernetes. Nothing about it
    is k8s- or provider-specific, and `api/*` is for provider SDK code, so it belongs here.
    """
    if not iso_timestamp:
        return ""
    parsed = parse_timestamp(iso_timestamp)
    if parsed is None:
        return iso_timestamp
    total_seconds = int((datetime.now(UTC) - parsed).total_seconds())

    if total_seconds < 60:
        return f"{total_seconds}s ago"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"
