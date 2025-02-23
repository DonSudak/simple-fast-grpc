from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google.protobuf.message import Message

from fast_grpc.core.context import ControllerContext
from fast_grpc.middleware.base import BaseMiddleware

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import NotIterableMethodType


class NotIterableSchedulerMiddleware(BaseMiddleware):
    """
    Middleware for injecting a scheduler into non-iterable method contexts.

    Adds an AsyncIOScheduler instance to the service context for use in method execution.
    """

    def __init__(self, scheduler: AsyncIOScheduler) -> None:
        """
        Initialize the scheduler middleware.

        Args:
            scheduler: The AsyncIOScheduler instance to inject into the context.
        """
        super().__init__()
        self._scheduler = scheduler

    async def __call__(
        self,
        method: "NotIterableMethodType",
        request: Message,
        context: ControllerContext,
        *args,
        **kwargs,
    ) -> Message:
        """
        Inject the scheduler into the context and execute the method.

        Args:
            method: The non-iterable method to process.
            request: The incoming gRPC request message.
            context: The service context to modify and pass to the method.
            *args: Additional positional arguments for the method.
            **kwargs: Additional keyword arguments for the method.

        Returns:
            Message: The response message from the method execution.
        """
        context.__setattr__("scheduler", self._scheduler)
        return await method(request, context, *args, **kwargs)
