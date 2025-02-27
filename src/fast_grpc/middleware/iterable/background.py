from collections.abc import AsyncGenerator, AsyncIterable, Coroutine
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fast_grpc.core.context import ControllerContext
from fast_grpc.middleware.base import BaseIterableMiddleware

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import IterableMethodType


class IterableSchedulerMiddleware(BaseIterableMiddleware):
    """
    Middleware for injecting a scheduler into iterable gRPC method contexts.

    Adds an AsyncIOScheduler instance to the service context for use in method execution.
    """

    def __init__(self, scheduler: AsyncIOScheduler) -> None:
        """
        Initialize the scheduler middleware for iterable methods.

        Args:
            scheduler: The AsyncIOScheduler instance to inject into the context.
        """
        super().__init__()
        self._scheduler = scheduler

    async def __call__(
        self,
        method: "IterableMethodType",
        request: AsyncIterable,
        context: ControllerContext,
        *args,
        **kwargs,
    ) -> AsyncGenerator | Coroutine:
        """
        Inject the scheduler into the context and execute the iterable method.

        Args:
            method: The iterable method to process.
            request: The incoming gRPC request as an async iterable.
            context: The service context to modify and pass to the method.
            *args: Additional positional arguments for the method.
            **kwargs: Additional keyword arguments for the method.

        Returns:
            Union[AsyncGenerator, Coroutine]: An async generator or coroutine yielding responses.
        """
        context.__setattr__("scheduler", self._scheduler)
        async for response in method(request, context, *args, **kwargs):
            yield response