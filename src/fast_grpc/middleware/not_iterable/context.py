from typing import TYPE_CHECKING

from google.protobuf.message import Message
from grpc.aio import ServicerContext

from fast_grpc.core.context import ControllerContext
from fast_grpc.middleware.base import BaseMiddleware

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import NotIterableMethodType


class NotIterableContextMiddleware(BaseMiddleware):
    """
    Middleware for injecting ServiceContext into non-iterable gRPC methods.

    Wraps the raw ControllerContext with a ServiceContext instance if a method descriptor is provided.
    """

    async def __call__(
        self,
        method: "NotIterableMethodType",
        request: Message,
        context: ServicerContext,
        *args,
        **kwargs,
    ) -> Message:
        """
        Process a non-iterable method call by adding a ServiceContext.

        Args:
            method: The non-iterable method to process.
            request: The incoming gRPC request message.
            context: The raw gRPC ServicerContext.
            *args: Additional positional arguments for the method.
            **kwargs: Additional keyword arguments, including an optional 'method_descriptor'.

        Returns:
            Message: The response message from the method execution.

        Raises:
            Exception: If 'method_descriptor' is not provided in kwargs.
        """
        if method_descriptor := kwargs.pop("method_descriptor", None):
            srv_context = ControllerContext(context, method, method_descriptor)
            return await method(request, srv_context, *args, **kwargs)
        raise Exception("Not found descriptor in context middleware")
