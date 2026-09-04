from collections.abc import Sequence

type StrOrSequence = str | Sequence
type OptionalStrOrSequence = StrOrSequence | None


def split_optional_str_or_sequence(input_argument: OptionalStrOrSequence) -> Sequence[str]:
    """Ensure return value is a tuple of strings"""

    if input_argument is None:
        return ()

    if isinstance(input_argument, Sequence):
        return tuple(input_argument)

    return tuple(input_argument.split(","))
