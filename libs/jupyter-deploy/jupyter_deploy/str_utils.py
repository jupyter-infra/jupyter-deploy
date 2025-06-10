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
