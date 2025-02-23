from typing import TYPE_CHECKING, AsyncGenerator, Coroutine

from google.protobuf.message import Message
from grpc.aio import ServicerContext

from fast_grpc.core.context import ControllerContext
from fast_grpc.middleware.base import BaseIterableMiddleware

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import IterableMethodType


class IterableContextMiddleware(BaseIterableMiddleware):
    """
    Middleware for injecting ServiceContext into iterable gRPC methods.

    Wraps the raw ServicerContext with a ServiceContext instance if a method descriptor is provided.
    """

    async def __call__(
        self,
        method: "IterableMethodType",
        request: Message,
        context: ServicerContext,
        *args,
        **kwargs,
    ) -> AsyncGenerator | Coroutine:
        """
        Process an iterable method call by adding a ServiceContext.

        Args:
            method: The iterable method to process.
            request: The incoming gRPC request message.
            context: The raw gRPC ServicerContext.
            *args: Additional positional arguments for the method.
            **kwargs: Additional keyword arguments, including an optional 'method_descriptor'.

        Returns:
            Union[AsyncGenerator, Coroutine]: An async generator or coroutine yielding responses.

        Notes:
            Requires 'method_descriptor' in kwargs to create a ServiceContext.
        """
        if method_descriptor := kwargs.pop("method_descriptor", None):
            srv_context = ControllerContext(context, method, method_descriptor)
            async for response in method(request, srv_context, *args, **kwargs):
                yield response