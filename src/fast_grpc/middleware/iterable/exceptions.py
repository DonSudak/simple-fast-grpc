import grpc
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Callable,
    Coroutine,
    AsyncIterable,
)

from logzero import logger

from fast_grpc.core.context import ControllerContext
from fast_grpc.middleware.base import BaseIterableMiddleware
from fast_grpc.utils import message_to_str

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import IterableMethodType


class IterableExceptionMiddleware(BaseIterableMiddleware):
    """
    Middleware for handling exceptions in iterable gRPC methods.

    Catches exceptions during method execution, logs them, and aborts the context with appropriate details.
    """

    def __init__(self, exception_handlers: dict[type[Exception], Callable]) -> None:
        """
        Initialize the exception handling middleware for iterable methods.

        Args:
            exception_handlers: Dictionary mapping exception types to their handler functions.
        """
        self._exception_handlers = exception_handlers

    async def __call__(
        self,
        method: "IterableMethodType",
        request: AsyncIterable,
        context: ControllerContext,
        *args,
        **kwargs,
    ) -> AsyncGenerator | Coroutine:
        """
        Execute an iterable method with exception handling.

        Args:
            method: The iterable method to process.
            request: The incoming gRPC request as an async iterable.
            context: The service context for execution details.
            *args: Additional positional arguments for the method.
            **kwargs: Additional keyword arguments for the method.

        Returns:
            Union[AsyncGenerator, Coroutine]: An async generator or coroutine yielding responses if successful.

        Raises:
            grpc.RpcError: Propagates gRPC-specific errors with logging and context abortion.
            Exception: Propagates other exceptions with logging and context abortion.
        """
        try:
            async for response in method(request, context, *args, **kwargs):
                yield response
        except grpc.RpcError as exc:
            logger.error(f"GRPC Error: {exc}")
            await context.abort(code=grpc.StatusCode.UNKNOWN, details=str(exc))
        except Exception as exc:
            logger.error(
                f"Unexpected Error: {context.controller_method.name}({message_to_str(request)}) "
                f"[ERR] {context.elapsed_time} ms\n{exc}"
            )
            if exception_handler := self._exception_handlers.get(type(exc)):
                await exception_handler(request, context, exc)
            await context.abort(code=grpc.StatusCode.UNKNOWN, details=str(exc))
