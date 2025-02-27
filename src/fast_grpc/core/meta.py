import abc
from collections.abc import AsyncIterable
from typing import Any, Callable, get_origin

from pydantic import BaseModel

from fast_grpc.core.controller import Controller
from fast_grpc.handlers.methods import (
    UnaryUnaryMethod,
    UnaryStreamMethod,
    StreamUnaryMethod,
    StreamStreamMethod,
    MethodType,
)
from fast_grpc.middleware.base import BaseMiddleware, BaseIterableMiddleware


class ControllerMeta(abc.ABCMeta):
    """
    Metaclass for automatically creating gRPC services from class definitions.

    This metaclass processes class attributes to define service methods based on
    annotations and static methods, registering them with a Service instance.
    """

    __controllers: dict[str, Controller] = {}

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        dct: dict[str, Any],
        proto_path: str = "",
        middlewares: list[BaseMiddleware | BaseIterableMiddleware] | None = None,
        exceptions: dict[type[Exception], Callable] | None = None,
    ) -> "ControllerMeta":
        """
        Create a new class instance and register it as a gRPC service.

        Args:
            name: The name of the class (will be lowercase for the service).
            bases: Tuple of base classes.
            dct: Dictionary of class attributes and methods.
            proto_path: Base path for the proto file (default: "").
            middlewares: Optional list of middleware to apply (default: None).
            exceptions: Optional dictionary of exception handlers (default: None).

        Returns:
            ControllerMeta: The newly created class instance.
        """
        name = name.lower()
        service = Controller(name=name, proto=proto_path + f"{name}.proto")

        middlewares_: list[BaseMiddleware | BaseIterableMiddleware] = middlewares or []
        exceptions_: dict[type[Exception], Callable] = exceptions or {}

        service.add_middleware(middlewares=middlewares_)
        service.add_exception_handler(exceptions=exceptions_)

        for endpoint in dct.values():
            if isinstance(endpoint, staticmethod):
                method_class: type[MethodType] = cls._get_method_type_by_annotations(
                    endpoint
                )
                service.add_method(
                    endpoint=endpoint,
                    method_class=method_class,
                )
        cls.__controllers |= {dct["__qualname__"]: service}
        return super().__new__(cls, name, bases, dct)

    @classmethod
    def _get_request_return_types(
        cls,
        request: Any,
        return_: Any,
    ) -> tuple[object, object]:
        """
        Extract base types from request and return annotations.

        Args:
            request: The request type annotation.
            return_: The return type annotation.

        Returns:
            Tuple[object, object]: A tuple of base types for request and return.
        """
        request = (
            request.__base__
            if hasattr(request, "__base__")
            else get_origin(request).__base__
        )
        return_ = (
            return_.__base__
            if hasattr(return_, "__base__")
            else get_origin(return_).__base__
        )
        return request, return_

    @classmethod
    def _get_method_type_by_annotations(cls, method: staticmethod) -> type[MethodType]:
        """
        Determine the method type based on its request and return annotations.

        Args:
            method: The static method to analyze.

        Returns:
            Type[MethodType]: The appropriate method type class (e.g., UnaryUnaryMethod).

        Raises:
            Exception: If the method lacks 'request' or 'return' annotations, or if types are unsupported.
        """
        annotations = method.__annotations__
        if not annotations.get("return"):
            raise Exception(f"No return in method {method.__name__}")

        if not annotations.get("request"):
            raise Exception(f"No request in method {method.__name__}")

        request_and_return_types = cls._get_request_return_types(
            request=annotations["request"], return_=annotations["return"]
        )

        annotations_and_method_types: dict[tuple[object, object], type[MethodType]] = {
            (BaseModel, BaseModel): UnaryUnaryMethod,
            (AsyncIterable, BaseModel): StreamUnaryMethod,
            (BaseModel, AsyncIterable): UnaryStreamMethod,
            (AsyncIterable, AsyncIterable): StreamStreamMethod,
        }

        if method_type := annotations_and_method_types.get(request_and_return_types):
            return method_type

        raise Exception(
            f"Request or return of the wrong types in method {method.__name__}"
        )

    def __call__(cls, *args, **kwargs) -> Controller:
        """
        Retrieve the registered Service instance for this class.

        Args:
            *args: Positional arguments (not used).
            **kwargs: Keyword arguments (not used).

        Returns:
            Controller: The Service instance associated with this class.
        """
        return cls.__controllers[cls.__qualname__]
