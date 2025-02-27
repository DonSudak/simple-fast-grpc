from pathlib import Path
from typing import (
    Type,
    Optional,
    Callable,
    AsyncIterator,
    TypeVar,
    Union,
    Any,
)

from logzero import logger
from pydantic import BaseModel

from fast_grpc.exceptions import base_exception_handlers
from fast_grpc.handlers.methods import (
    UnaryUnaryMethod,
    UnaryStreamMethod,
    StreamUnaryMethod,
    StreamStreamMethod,
    MethodType,
)
from fast_grpc.middleware import (
    MiddlewareManager,
    NotIterableContextMiddleware,
    NotIterableSchedulerMiddleware,
    NotIterableExceptionMiddleware,
    IterableContextMiddleware,
    IterableExceptionMiddleware,
    IterableSchedulerMiddleware,
    BaseMiddlewareManager,
    BaseMiddleware,
    BaseIterableMiddleware,
)
from fast_grpc.utils import import_proto_file

T = TypeVar("T")
R = TypeVar("R")


class Controller:
    """
    Represents a gRPC controller definition.

    This class encapsulates the configuration and management of gRPC controller methods,
    middleware, and exception handling.
    """

    def __init__(self, name: str, proto: str = "", scheduler=None) -> None:
        """
        Initialize a new gRPC controller.

        Args:
            name: The name of the gRPC controller.
            proto: Path to the proto file defining the controller (default: "").
            scheduler: Optional scheduler for background tasks (default: None).

        Raises:
            ValueError: If proto is provided but does not end with '.proto'.
        """
        if proto and not proto.endswith(".proto"):
            raise ValueError("Service proto must end with '.proto'")
        self.name: str = name
        self.proto: str = proto
        self.methods: dict[str, MethodType] = {}
        self.exception_handlers: dict[type[Exception], Callable] = {
            **base_exception_handlers
        }
        self.scheduler = scheduler

        self.middleware_manager: BaseMiddlewareManager = MiddlewareManager(
            middlewares=[
                NotIterableContextMiddleware(),
                NotIterableExceptionMiddleware(self.exception_handlers),
                *(
                    [NotIterableSchedulerMiddleware(self.scheduler)]
                    if self.scheduler
                    else []
                ),
            ],
            iterable_middlewares=[
                IterableContextMiddleware(),
                IterableExceptionMiddleware(self.exception_handlers),
                *(
                    [IterableSchedulerMiddleware(self.scheduler)]
                    if self.scheduler
                    else []
                ),
            ],
        )
        self.grpc_servicer = None

    @property
    def interface_name(self) -> str:
        """
        Get the gRPC interface name for the controller.

        Returns:
            str: The interface name in the format '<name>Servicer'.
        """
        return f"{self.name}Servicer"

    @property
    def proto_path(self) -> Path:
        """
        Get the Path object for the proto file.

        Returns:
            Path: The pathlib.Path object representing the proto file path.
        """
        return Path(self.proto)

    def add_method(
        self,
        endpoint: Callable,
        *,
        name: Optional[str] = None,
        method_class: type[MethodType] = UnaryUnaryMethod,
        **kwargs,
    ) -> MethodType:
        """
        Add a method to the controller.

        Args:
            endpoint: The callable endpoint to register.
            name: Optional custom name for the method (default: None).
            method_class: The type of method to instantiate (default: UnaryUnaryMethod).
            **kwargs: Additional keyword arguments for the method class.

        Returns:
            MethodType: The registered method instance.
        """
        method = method_class(name=name, endpoint=endpoint, **kwargs)
        self.methods[method.name] = method
        return method

    def unary_unary(
        self,
        name: Optional[str] = None,
        *,
        request_model: Optional[type[BaseModel]] = None,
        response_model: Optional[type[BaseModel]] = None,
        description: str = "",
    ) -> Callable:
        """
        Decorator for defining a unary-unary gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the unary-unary method.
        """

        def decorator(endpoint: Callable[[T], R]) -> Callable[[T], R]:
            self.add_method(
                name=name,
                endpoint=endpoint,
                method_class=UnaryUnaryMethod,
                request_model=request_model,
                response_model=response_model,
                description=description,
            )
            return endpoint

        return decorator

    def unary_stream(
        self,
        name: Optional[str] = None,
        *,
        request_model: Optional[type[BaseModel]] = None,
        response_model: Optional[type[BaseModel]] = None,
        description: str = "",
    ) -> Callable:
        """
        Decorator for defining a unary-stream gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the unary-stream method.
        """

        def decorator(
            endpoint: Callable[[T], AsyncIterator[R]]
        ) -> Callable[[T], AsyncIterator[R]]:
            self.add_method(
                name=name,
                endpoint=endpoint,
                method_class=UnaryStreamMethod,
                request_model=request_model,
                response_model=response_model,
                description=description,
            )
            return endpoint

        return decorator

    def stream_unary(
        self,
        name: Optional[str] = None,
        *,
        request_model: Optional[type[BaseModel]] = None,
        response_model: Optional[type[BaseModel]] = None,
        description: str = "",
    ) -> Callable:
        """
        Decorator for defining a stream-unary gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the stream-unary method.
        """

        def decorator(
            endpoint: Callable[[AsyncIterator[T]], R]
        ) -> Callable[[AsyncIterator[T]], R]:
            self.add_method(
                name=name,
                endpoint=endpoint,
                method_class=StreamUnaryMethod,
                request_model=request_model,
                response_model=response_model,
                description=description,
            )
            return endpoint

        return decorator

    def stream_stream(
        self,
        name: Optional[str] = None,
        *,
        request_model: Optional[type[BaseModel]] = None,
        response_model: Optional[type[BaseModel]] = None,
        description: str = "",
    ) -> Callable:
        """
        Decorator for defining a stream-stream gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the stream-stream method.
        """

        def decorator(
            endpoint: Callable[[AsyncIterator[T]], AsyncIterator[R]]
        ) -> Callable[[AsyncIterator[T]], AsyncIterator[R]]:
            self.add_method(
                name=name,
                endpoint=endpoint,
                method_class=StreamStreamMethod,
                request_model=request_model,
                response_model=response_model,
                description=description,
            )
            return endpoint

        return decorator

    def __str__(self) -> str:
        """
        Return a string representation of the controller.

        Returns:
            str: A string in the format 'Service(name=<name>, proto=<proto>)'.
        """
        return f"{self.__class__.__name__}(name={self.name}, proto={self.proto})"

    def add_middleware(
        self, middlewares: list[Union[BaseMiddleware, BaseIterableMiddleware]]
    ) -> None:
        """
        Add middleware to the controller.

        Args:
            middlewares: List of middleware instances to apply.
        """
        iterable_middlewares: list[BaseIterableMiddleware] = [
            middleware
            for middleware in middlewares
            if isinstance(middleware, BaseIterableMiddleware)
        ]
        simple_middlewares: list[BaseMiddleware] = [
            middleware
            for middleware in middlewares
            if isinstance(middleware, BaseMiddleware)
        ]
        self.middleware_manager.register_iterable(iterable_middlewares)
        self.middleware_manager.register(simple_middlewares)

    def add_exception_handler(
        self, exceptions: dict[type[Exception], Callable]
    ) -> None:
        """
        Register exception handlers for the controller.

        Args:
            exceptions: Dictionary mapping exception types to their handler functions.
        """
        self.exception_handlers |= exceptions

    def add_to_server(self, server: Any) -> Optional[Any]:
        """
        Register the controller with a gRPC server.

        Args:
            server: The gRPC server instance to add the controller to.

        Returns:
            Optional[Any]: The gRPC controller instance if successful, None if already bound or no methods.

        Notes:
            Logs a message if the controller is already bound or has no methods.
        """
        if self.grpc_servicer is not None:
            logger.info("Service already bound to server")
            return None
        name = self.name
        proto = self.proto_path
        methods = self.methods
        if not methods:
            logger.info(f"{self} add_to_server [Ignored] -> no methods")
            return None
        interface_name = f"{name}Servicer"
        pb2, pb2_grpc = import_proto_file(proto)
        interface_class = getattr(pb2_grpc, interface_name)
        self.grpc_servicer = make_grpc_service_from_methods(
            pb2, name, interface_class, methods, self.middleware_manager
        )
        pb2_grpc_add_func = getattr(pb2_grpc, f"add_{interface_name}_to_server")
        pb2_grpc_add_func(self.grpc_servicer(), server)
        logger.info(f"{self} add_to_server success")
        return self.grpc_servicer


def make_grpc_service_from_methods(
    pb2: Any,
    controller_name: str,
    interface_class: Type,
    methods: dict[str, MethodType],
    middleware_manager: BaseMiddlewareManager,
) -> Type:
    """
    Create a gRPC controller class from method definitions.

    Args:
        pb2: The compiled proto module.
        controller_name: The name of the controller.
        interface_class: The base interface class from the gRPC generated code.
        methods: Dictionary of method instances to register.
        middleware_manager: Manager for applying middleware to methods.

    Returns:
        Type: The dynamically created controller class.

    Raises:
        RuntimeError: If a method name is not found in the controller descriptor.
    """

    def create_method(method: MethodType) -> Callable:
        if method.name not in controller_descriptor.methods_by_name:
            raise RuntimeError(f"Method '{method.name}' not found")
        method_descriptor = controller_descriptor.methods_by_name[method.name]
        method.name = f"{controller_descriptor.full_name}.{method_descriptor.name}"
        wrapped_method = middleware_manager.wraps_middleware(
            method=method,
            method_descriptor=method_descriptor,
        )
        return wrapped_method

    controller_descriptor = pb2.DESCRIPTOR.services_by_name[controller_name]
    return type(
        controller_name,
        (interface_class,),
        {name: create_method(method) for name, method in methods.items()},
    )
