from typing import Any, Callable


def retry_condition_except_on_exceptions(
    *exceptions: type[BaseException],
) -> Callable[[Any, Any, Any], bool]:

    def retry_handler(_, __, state) -> bool:
        """Retry handler that skips retries if the exception is one of the
        specified types."""
        try:
            state.result()
        except BaseException as exc:
            if isinstance(exc, exceptions):
                return False
        return True

    return retry_handler
