from abc import ABC, abstractmethod
from typing import Callable, TYPE_CHECKING, AsyncIterable, Coroutine

from fast_grpc.core.context import ControllerContext
from google.protobuf.message import Message
from typing import AsyncGenerator

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import (
        IterableMethodType,
        NotIterableMethodType,
        MethodType,
    )


class BaseMiddleware(ABC):
    """
    Abstract base class for non-iterable gRPC middleware.

    Defines the interface for middleware handling methods with non-iterable responses.
    """

    @abstractmethod
    async def __call__(
        self,
        method: "NotIterableMethodType",
        request: Message,
        context: ControllerContext,
        *args,
        **kwargs,
    ) -> Message:
        """
        Process a non-iterable gRPC method call.

        Args:
            method: The non-iterable method to process.
            request: The incoming gRPC request message.
            context: The service context providing execution details.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Message: The processed response message.

        Notes:
            This method must be implemented by subclasses.
        """
        ...


class BaseIterableMiddleware(ABC):
    """
    Abstract base class for iterable gRPC middleware.

    Defines the interface for middleware handling methods with iterable responses.
    """

    @abstractmethod
    async def __call__(
        self,
        method: "IterableMethodType",
        request: AsyncIterable,
        context: ControllerContext,
        *args,
        **kwargs,
    ) -> AsyncGenerator | Coroutine:
        """
        Process an iterable gRPC method call.

        Args:
            method: The iterable method to process.
            request: The incoming gRPC request as an async iterable.
            context: The service context providing execution details.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Union[AsyncGenerator, Coroutine]: An async generator or coroutine yielding responses.

        Notes:
            This method must be implemented by subclasses.
        """
        ...


class BaseMiddlewareManager(ABC):
    """
    Abstract base class for managing gRPC middleware.

    Defines the interface for registering and applying middleware to methods.
    """

    @abstractmethod
    def register(self, middlewares: list[BaseMiddleware]) -> None:
        """
        Register non-iterable middleware instances.

        Args:
            middlewares: List of BaseMiddleware instances to register.

        Notes:
            This method must be implemented by subclasses.
        """
        ...

    @abstractmethod
    def register_iterable(self, middlewares: list[BaseIterableMiddleware]) -> None:
        """
        Register iterable middleware instances.

        Args:
            middlewares: List of BaseIterableMiddleware instances to register.

        Notes:
            This method must be implemented by subclasses.
        """
        ...

    @abstractmethod
    def wraps_middleware(self, method: "MethodType", *args, **kwargs) -> Callable:
        """
        Apply middleware to a gRPC method.

        Args:
            method: The method to wrap with middleware.
            *args: Additional positional arguments for middleware.
            **kwargs: Additional keyword arguments for middleware.

        Returns:
            Callable: The wrapped method with middleware applied.

        Notes:
            This method must be implemented by subclasses.
        """
        ...
