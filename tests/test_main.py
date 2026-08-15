from deepseek_vision_mcp.main import _contains_keyboard_interrupt


class _SyntheticGroup(BaseException):
    def __init__(self, *exceptions: BaseException) -> None:
        self.exceptions = exceptions


def test_contains_keyboard_interrupt_recurses_without_exceptiongroup_dependency():
    assert _contains_keyboard_interrupt(KeyboardInterrupt()) is True
    assert _contains_keyboard_interrupt(_SyntheticGroup(ValueError(), KeyboardInterrupt())) is True
    assert _contains_keyboard_interrupt(_SyntheticGroup(ValueError())) is False
