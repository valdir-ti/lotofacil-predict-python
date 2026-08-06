"""Shared validation helpers for Lotofacil game numbers."""


class InvalidGameError(ValueError):
    pass


def validate_numbers(numbers):
    """Validate that ``numbers`` is a list of 15 unique integers between 1 and 25.

    Returns the sorted list of parsed integers.
    """
    if not isinstance(numbers, (list, tuple)):
        raise InvalidGameError('numbers must be a list.')
    if len(numbers) != 15:
        raise InvalidGameError('A game must have exactly 15 numbers.')

    parsed = []
    for value in numbers:
        try:
            parsed_value = int(value)
        except (TypeError, ValueError):
            raise InvalidGameError(f'Invalid number: {value!r}')
        if not (1 <= parsed_value <= 25):
            raise InvalidGameError(f'Number out of range (1-25): {parsed_value}')
        parsed.append(parsed_value)

    if len(set(parsed)) != 15:
        raise InvalidGameError('Numbers must be unique.')

    return sorted(parsed)
