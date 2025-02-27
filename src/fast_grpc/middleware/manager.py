import functools
from typing import TYPE_CHECKING, AsyncIterable, Callable

from fast_grpc.core.dependencies import Dependencies
from fast_grpc.middleware.base import (
    BaseMiddleware,
    BaseMiddlewareManager,
    BaseIterableMiddleware,
)

if TYPE_CHECKING:
    from fast_grpc.handlers.methods import MethodType


class BaseWrapper:
    """
    Base class for wrapping callable methods with dependencies.
    """

    def __init__(
        self,
        func: Callable,
        name: str,
        dependencies: Dependencies | None = None,
    ) -> None:
        """
        Initialize the wrapper with a function and optional dependencies.

        Args:
            func: The callable to wrap.
            name: The name of the wrapped method.
            dependencies: Optional dependencies to resolve (default: None).
        """
        self.func = func
        self.name = name
        self.dependencies = dependencies


class AsyncGeneratorWrapper(BaseWrapper):
    """Wrapper for methods returning asynchronous generators."""

    def __init__(
        self,
        func: Callable,
        name: str,
        dependencies: Dependencies | None = None,
    ) -> None:
        """
        Initialize the async generator wrapper.

        Args:
            func: The callable to wrap.
            name: The name of the wrapped method.
            dependencies: Optional dependencies to resolve (default: None).
        """
        super().__init__(func, name, dependencies)

    async def __call__(self, *args, **kwargs) -> AsyncIterable:
        """
        Execute the wrapped function and yield its results.

        Resolves dependencies if present and yields results from the async generator.

        Args:
            *args: Positional arguments to pass to the wrapped function.
            **kwargs: Keyword arguments to pass to the wrapped function.

        Returns:
            AsyncIterable: An asynchronous iterable yielding the function's results.
        """
        if self.dependencies:
            kwargs |= await self.dependencies.get_dependencies_results()
        async for response in self.func(*args, **kwargs):
            yield response


class AsyncFunctionWrapper(BaseWrapper):
    """Wrapper for methods returning asynchronous results."""

    def __init__(
        self,
        func: Callable,
        name: str,
        dependencies: Dependencies | None = None,
    ) -> None:
        """
        Initialize the async function wrapper.

        Args:
            func: The callable to wrap.
            name: The name of the wrapped method.
            dependencies: Optional dependencies to resolve (default: None).
        """
        super().__init__(func, name, dependencies)

    async def __call__(self, *args, **kwargs) -> Callable:
        """
        Execute the wrapped function and return its result.

        Resolves dependencies if present and returns the async function's result.

        Args:
            *args: Positional arguments to pass to the wrapped function.
            **kwargs: Keyword arguments to pass to the wrapped function.

        Returns:
            Callable: The result of the wrapped async function.
        """
        if self.dependencies:
            kwargs |= await self.dependencies.get_dependencies_results()
        return await self.func(*args, **kwargs)


class MiddlewareManager(BaseMiddlewareManager):
    """Manager for applying middleware to gRPC methods."""

    def __init__(
        self,
        middlewares: list[BaseMiddleware],
        iterable_middlewares: list[BaseIterableMiddleware],
    ) -> None:
        """
        Initialize the middleware manager with separate middleware lists.

        Args:
            middlewares: List of non-iterable middleware instances.
            iterable_middlewares: List of iterable middleware instances.
        """
        self._middlewares = middlewares
        self._iterable_middlewares = iterable_middlewares

    def register(self, middlewares: list[BaseMiddleware]) -> None:
        """
        Register additional non-iterable middleware.

        Args:
            middlewares: List of BaseMiddleware instances to add.
        """
        self._middlewares.extend(middlewares)

    def register_iterable(self, middlewares: list[BaseIterableMiddleware]) -> None:
        """
        Register additional iterable middleware.

        Args:
            middlewares: List of BaseIterableMiddleware instances to add.
        """
        self._iterable_middlewares.extend(middlewares)

    def wraps_middleware(
        self,
        method: "MethodType",
        *args,
        **kwargs,
    ) -> Callable:
        """
        Wrap a method with applicable middleware.

        Chooses between iterable and non-iterable wrappers based on the method's response type.

        Args:
            method: The MethodType instance to wrap.
            *args: Additional positional arguments for middleware.
            **kwargs: Additional keyword arguments for middleware.

        Returns:
            Callable: The wrapped method with middleware applied.
        """
        if method.is_response_iterable:
            method_wrapper_class = AsyncGeneratorWrapper
            middlewares = self._iterable_middlewares
        else:
            method_wrapper_class = AsyncFunctionWrapper
            middlewares = self._middlewares

        wrapped = method_wrapper_class(
            method,
            method.name,
        )

        for m in reversed(middlewares):
            wrapped = method_wrapper_class(
                functools.partial(m, wrapped, *args, **kwargs),
                wrapped.name,
            )
        wrapped.dependencies = method.dependencies
        method_wrapper = self._create_method_wrapper(wrapped=wrapped)
        method_wrapper.__name__ = wrapped.name
        return method_wrapper

    def _create_method_wrapper(
        self, wrapped: AsyncFunctionWrapper | AsyncGeneratorWrapper
    ) -> Callable:
        """
        Create a method wrapper based on the wrapper type.

        Args:
            wrapped: The wrapped instance (AsyncFunctionWrapper or AsyncGeneratorWrapper).

        Returns:
            Callable: A method wrapper tailored to the wrapper type.
        """
        if isinstance(wrapped, AsyncGeneratorWrapper):
            return self._create_async_generator_method_wrapper(wrapped)
        return self._create_async_function_method_wrapper(wrapped)

    @staticmethod
    def _create_async_generator_method_wrapper(
        wrapped: AsyncGeneratorWrapper,
    ) -> Callable:
        """
        Create a wrapper for async generator methods.

        Args:
            wrapped: The AsyncGeneratorWrapper instance to wrap.

        Returns:
            Callable: An async wrapper yielding responses from the wrapped method.
        """

        async def async_generator_method_wrapper(self, request, context):
            async for response in wrapped(request, context):
                yield response

        return async_generator_method_wrapper

    @staticmethod
    def _create_async_function_method_wrapper(
        wrapped: AsyncFunctionWrapper,
    ) -> Callable:
        """
        Create a wrapper for async function methods.

        Args:
            wrapped: The AsyncFunctionWrapper instance to wrap.

        Returns:
            Callable: An async wrapper returning the result of the wrapped method.
        """

        async def async_function_method_wrapper(self, request, context):
            return await wrapped(request, context)

        return async_function_method_wrapper
