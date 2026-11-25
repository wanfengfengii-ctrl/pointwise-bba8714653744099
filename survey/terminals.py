from dataclasses import dataclass


def validate_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f'{label} must be a nonempty name without surrounding space')
    value.encode('utf-8')
    return value


@dataclass(frozen=True, slots=True)
class TerminalSet:
    names: tuple[str, str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.names, tuple) or len(self.names) != 3:
            raise ValueError('exactly three public terminals are required')
        for name in self.names:
            validate_name(name, 'terminal')
        if len(set(self.names)) != 3:
            raise ValueError('public terminal names must be distinct')


def validate_terminal_set(names: object) -> TerminalSet:
    if not isinstance(names, (list, tuple)) or len(names) != 3:
        raise ValueError('exactly three public terminals are required')
    return TerminalSet(tuple(names))
