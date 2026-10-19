from collections.abc import Sequence

type StrOrSequence = str | Sequence
type OptionalStrOrSequence = StrOrSequence | None


def split_optional_str_or_sequence(input_argument: OptionalStrOrSequence) -> Sequence[str]:
    """
    Ensure return value is a tuple of strings.  There are other subclasses of Sequence but they
    remain obscure enough in this usage to not be accounted for.
    """

    if input_argument is None:
        return ()

    if isinstance(input_argument, str):
        return tuple(input_argument.split(","))

    return tuple(input_argument)
