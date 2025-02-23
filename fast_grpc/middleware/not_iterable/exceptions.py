import grpc
from typing import TYPE_CHECKING, Callable, Dict, Type

from google.protobuf.message import Message
from logzero import logger

from fast_grpc.core.context import ControllerContext
from fast_grpc.middleware.base import BaseMiddleware
from fast_grpc.utils import message_to_str

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import NotIterableMethodType


class NotIterableExceptionMiddleware(BaseMiddleware):
    """
    Middleware for handling exceptions in non-iterable gRPC methods.

    Catches exceptions during method execution, logs them, and aborts the context with appropriate details.
    """

    def __init__(self, exception_handlers: Dict[Type[Exception], Callable]) -> None:
        """
        Initialize the exception handling middleware.

        Args:
            exception_handlers: Dictionary mapping exception types to their handler functions.
        """
        self._exception_handlers = exception_handlers

    async def __call__(
        self,
        method: "NotIterableMethodType",
        request: Message,
        context: ControllerContext,
        *args,
        **kwargs,
    ) -> Message:
        """
        Execute a non-iterable method with exception handling.

        Args:
            method: The non-iterable method to process.
            request: The incoming gRPC request message.
            context: The service context for execution details.
            *args: Additional positional arguments for the method.
            **kwargs: Additional keyword arguments for the method.

        Returns:
            Message: The response message from the method execution if successful.

        Raises:
            grpc.RpcError: Propagates gRPC-specific errors with logging and context abortion.
            Exception: Propagates other exceptions with logging and context abortion.
        """
        try:
            return await method(request, context, *args, **kwargs)
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
