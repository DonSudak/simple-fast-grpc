import functools
from typing import Callable

import grpc
from google.protobuf.message import Message
from pydantic import ValidationError

from fast_grpc.core.context import ControllerContext
from fast_grpc.exceptions.exceptions import GRPCException


class ExceptionsHandlers:
    """
    Handler class for managing gRPC and Pydantic exceptions.

    Provides class methods to process specific exception types and abort the context accordingly.
    """

    @classmethod
    async def _grpc_exception_handler(
        cls,
        _: Message,
        context: ControllerContext,
        exc: GRPCException,
    ) -> None:
        """
        Handle GRPCException by aborting the context with the exception's status and details.

        Args:
            _: The gRPC message (unused).
            context: The controller context to abort.
            exc: The GRPCException instance containing status and details.
        """
        await context.abort(code=exc.status, details=exc.details)

    @classmethod
    async def _pydantic_exception_handler(
        cls,
        _: Message,
        context: ControllerContext,
        exc: ValidationError,
    ) -> None:
        """
        Handle ValidationError from Pydantic by aborting the context with error details.

        Extracts the first error from the ValidationError and constructs a detailed message.

        Args:
            _: The gRPC message (unused).
            context: The controller context to abort.
            exc: The ValidationError instance containing validation errors.
        """
        exception = exc.errors()[0]
        details = f"{exception['msg']}. Location: {exception['loc']}. Input: {exception['input']}"
        await context.abort(code=grpc.StatusCode.UNKNOWN, details=details)


base_exception_handlers: dict[type[Exception], Callable] = {
    method.__annotations__["exc"]: functools.partial(
        method.__func__, ExceptionsHandlers
    )
    for method in ExceptionsHandlers.__dict__.values()
    if isinstance(method, classmethod)
}
"""
Default exception handlers for the FastGRPC framework.

Maps exception types (GRPCException, ValidationError) to their respective handler functions
from the ExceptionsHandlers class, wrapped with functools.partial to bind the class.
"""
