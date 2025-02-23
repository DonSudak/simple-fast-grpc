import asyncio
import functools
import inspect
from typing import Any, Callable, Dict, Optional


class Depends:
    """
    Dependency injection handler for resolving function dependencies.

    This class manages the resolution of dependencies specified in function signatures.
    """

    def __init__(self, dependency: Callable[..., Any]) -> None:
        """
        Initialize the Depends instance with a dependency function.

        Args:
            dependency: The callable dependency to resolve.
        """
        self.dependency = dependency
        self._cached_dependencies: list[Any] = []

    async def resolve_dependencies(
        self,
        func: Callable[..., Any],
        cache: Optional[Dict[Callable, Any]] = None,
    ) -> Any:
        """
        Recursively resolve dependencies for a function and execute it.

        This method parses the function signature, resolves any nested dependencies marked
        with Depends, and returns the result of the function call with substituted values.

        Args:
            func: The function whose dependencies need to be resolved.
            cache: Optional dictionary to cache resolved dependency results (default: None).

        Returns:
            Any: The result of the function call with resolved dependencies.

        Raises:
            StopIteration: If a generator dependency runs out of values.
            StopAsyncIteration: If an async generator dependency runs out of values.
        """
        if cache is None:
            cache = {}

        sig = inspect.signature(func)
        kwargs: Dict[str, Any] = {}

        for name, param in sig.parameters.items():
            if isinstance(param.default, self.__class__):
                dep_func = param.default.dependency
                if dep_func in cache:
                    dep_value = cache[dep_func]
                else:
                    dep_value = await self.resolve_dependencies(dep_func, cache)
                    cache[dep_func] = dep_value
                kwargs[name] = dep_value
            else:
                kwargs[name] = param.default

        result = func(**kwargs)

        if inspect.isgenerator(result):
            self._cached_dependencies.append(result)
            return next(result)
        if asyncio.iscoroutine(result):
            return await result
        if inspect.isasyncgen(result):
            self._cached_dependencies.append(result)
            return await anext(result)
        return result

    async def __call__(self) -> tuple[Any, list[Any]]:
        """
        Simulate calling the dependency with all its dependencies resolved.

        Returns:
            tuple[Any, List[Any]]: A tuple containing the resolved dependency result
                                   and a list of cached generator dependencies.
        """
        return await self.resolve_dependencies(self.dependency), self._cached_dependencies


class Dependencies:
    """
    Manager for endpoint dependencies.

    This class handles the resolution and caching of dependencies for a given endpoint.
    """

    def __init__(self, endpoint: Callable) -> None:
        """
        Initialize the EndpointDependencies with an endpoint.

        Args:
            endpoint: The endpoint function to analyze for dependencies.
        """
        self.endpoint_dependencies: Dict[str, Depends] = self._get_endpoint_dependencies(endpoint)
        self._cached_dependencies: list[Any] = []

    def get_close_dependencies_wrapped_endpoint(self, endpoint: Callable) -> Callable[..., Any]:
        """
        Wrap the endpoint to close generator dependencies after execution.

        Args:
            endpoint: The original endpoint function to wrap.

        Returns:
            Callable[..., Any]: A wrapped async function that manages dependency cleanup.
        """
        @functools.wraps(endpoint)
        async def wrapper(*args, **kwargs) -> Any:
            result = await endpoint(*args, **kwargs)
            for gen_dependency in self._cached_dependencies:
                try:
                    if inspect.isgenerator(gen_dependency):
                        next(gen_dependency)
                    elif inspect.isasyncgen(gen_dependency):
                        await anext(gen_dependency)
                except (StopAsyncIteration, StopIteration):
                    pass
            return result
        return wrapper

    async def get_dependencies_results(self) -> Dict[str, Dict[str, Any]]:
        """
        Resolve all dependencies for the endpoint and return their results.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary containing a nested dictionary
                                       of dependency results keyed by parameter names.
        """
        dependencies_results: Dict[str, Any] = {}
        for param, dependency in self.endpoint_dependencies.items():
            dependency_last_handler, _gen_dependencies = await dependency()
            if _gen_dependencies:
                self._cached_dependencies.extend(_gen_dependencies)

            if inspect.isgenerator(dependency_last_handler):
                self._cached_dependencies.append(dependency_last_handler)
                dependencies_results |= {param: next(dependency_last_handler)}
                continue

            if asyncio.iscoroutine(dependency_last_handler):
                dependencies_results |= {param: await dependency_last_handler}
                continue

            if inspect.isasyncgen(dependency_last_handler):
                self._cached_dependencies.append(dependency_last_handler)
                dependency_last_handler = await anext(dependency_last_handler)

            dependencies_results |= {param: dependency_last_handler}
        return {"dependencies_results": dependencies_results}

    @staticmethod
    def _get_endpoint_dependencies(endpoint: Callable) -> Dict[str, "Depends"]:
        """
        Extract dependency instances from the endpoint's signature.

        Args:
            endpoint: The endpoint function to inspect.

        Returns:
            Dict[str, Depends]: A dictionary mapping parameter names to their Depends instances.
        """
        endpoint_signature_params = inspect.signature(endpoint).parameters
        return {
            k: v.default
            for k, v in endpoint_signature_params.items()
            if v.default != inspect.Parameter.empty and isinstance(v.default, Depends)
        }