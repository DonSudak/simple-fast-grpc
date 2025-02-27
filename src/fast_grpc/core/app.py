import asyncio
from typing import Callable, Optional, Any

import grpc
from grpc.aio._typing import ChannelArgumentType  # noqa
from grpc.aio import Server
from logzero import logger
from pydantic import BaseModel
from fast_grpc.middleware import BaseMiddleware, BaseIterableMiddleware

from fast_grpc.schema import ProtoBuilder
from .controller import Controller
from fast_grpc.handlers import (
    UnaryUnaryMethod,
    UnaryStreamMethod,
    StreamUnaryMethod,
    StreamStreamMethod,
)
from fast_grpc.utils import protoc_compile


class FastGRPC(object):
    """
    Main application class for the FastGRPC framework.

    This class serves as the primary entry point for defining and running gRPC services.

    Example:
        ```python
        from fast_grpc import FastGRPC

        app = FastGRPC(service_name="Greeter", proto="greeter.proto")
    """

    def __init__(
        self,
        *,
        service_name: str = "FastGRPC",
        proto: str = "fast_grpc.proto",
        auto_gen_proto: bool = True,
        scheduler=None,
    ):
        """
        Initialize the FastGRPC application.

        Args:
            service_name: The default name for the primary gRPC service (default: "FastGRPC").
            proto: Path to the proto file defining service schemas (default: "fast_grpc.proto").
            auto_gen_proto: If True, automatically generates proto files (default: True).
            scheduler: Optional scheduler for background tasks (default: None).
        """
        self.scheduler = scheduler
        self.service = Controller(
            name=service_name,
            proto=proto,
            scheduler=self.scheduler,
        )
        self._services: dict[str, Controller] = {f"{proto}:{service_name}": self.service}
        self._auto_gen_proto = auto_gen_proto

    def setup(self) -> None:
        """
        Prepare all services and their schemas for execution.

        This method generates proto files if auto_gen_proto is enabled and compiles them.
        """
        builders = {}
        for service in self._services.values():
            if not service.methods:
                continue
            if service.proto_path not in builders:
                builders[service.proto_path] = ProtoBuilder(
                    package=service.proto_path.stem
                )
            builders[service.proto_path].add_service(service)
        for proto, builder in builders.items():
            if self._auto_gen_proto:
                proto_define = builder.get_proto()
                content = proto_define.render_proto_file()
                proto.parent.mkdir(parents=True, exist_ok=True)
                proto.write_text(content)
                logger.info(f"Created {proto} file success")
            protoc_compile(proto)

    def unary_unary(
        self,
        name: Optional[str] = None,
        *,
        request_model: Optional[type[BaseModel]] = None,
        response_model: Optional[type[BaseModel]] = None,
        description: str = "",
    ):
        """
        Decorator for defining a unary-unary gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the method with the service.
        """

        def decorator(endpoint: Callable) -> Callable:
            self.service.add_method(
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
    ):
        """
        Decorator for defining a unary-stream gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the method with the service.
        """

        def decorator(endpoint: Callable) -> Callable:
            self.service.add_method(
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
    ):
        """
        Decorator for defining a stream-unary gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the method with the service.
        """

        def decorator(endpoint: Callable) -> Callable:
            self.service.add_method(
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
    ):
        """
        Decorator for defining a stream-stream gRPC method.

        Args:
            name: Optional custom name for the method (default: None).
            request_model: Pydantic model for the request (default: None).
            response_model: Pydantic model for the response (default: None).
            description: Description of the method (default: "").

        Returns:
            Callable: A decorator that registers the method with the service.
        """

        def decorator(endpoint: Callable) -> Callable:
            self.service.add_method(
                name=name,
                endpoint=endpoint,
                method_class=StreamStreamMethod,
                request_model=request_model,
                response_model=response_model,
                description=description,
            )
            return endpoint

        return decorator

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        server: Optional[Server] = None,
    ) -> None:
        """
        Run the gRPC server synchronously.

        Args:
            host: The host address to bind the server (default: "127.0.0.1").
            port: The port number to listen on (default: 50051).
            server: Optional pre-existing gRPC server instance (default: None).
        """
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            self.run_async(
                host=host,
                port=port,
                server=server,
            )
        )
        loop.close()

    async def run_async(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        server: Optional[Server] = None,
    ) -> None:
        """
        Run the gRPC server asynchronously.

        Args:
            host: The host address to bind the server (default: "127.0.0.1").
            port: The port number to listen on (default: 50051).
            server: Optional pre-existing gRPC server instance (default: None).
        """
        self.setup()
        if self.scheduler:
            self.scheduler.start()
        server_ = grpc.aio.server() if not server else server
        for service in self._services.values():
            service.add_to_server(server_)
        server_.add_insecure_port(f"{host}:{port}")
        await server_.start()
        logger.info(f"Running grpc on {host}:{port}")
        await server_.wait_for_termination()

    def add_service(self, service: Controller):
        """
        Add a new service to the application.

        Args:
            service: The Service instance to register.

        Notes:
            If the service lacks a proto file, it inherits the proto from the primary service.
        """
        if not service.proto:
            service.proto = self.service.proto
        path_name = f"{service.proto}:{service.name}"
        if path_name not in self._services:
            self._services[path_name] = Controller(
                name=service.name,
                proto=service.proto,
                scheduler=self.scheduler,
            )
        self._services[path_name].methods.update(service.methods)

    def add_to_server(self, server: Server) -> list[Any]:
        """
        Register all services with an existing gRPC server.

        Args:
            server: The gRPC server instance to add services to.

        Returns:
            List[any]: List of registered gRPC servicer instances.
        """
        grpc_services = []
        self.setup()
        for service in self._services.values():
            grpc_srv = service.add_to_server(server)
            if grpc_srv:
                grpc_services.append(grpc_srv)
        return grpc_services

    def add_exception_handler(
        self, exceptions: dict[type[Exception], Callable]
    ) -> None:
        """
        Register exception handlers for all services.

        Args:
            exceptions: Dictionary mapping exception types to their handler functions.
        """
        for service in self._services.values():
            service.add_exception_handler(exceptions)

    def add_middleware(
        self, middlewares: list[BaseMiddleware | BaseIterableMiddleware]
    ) -> None:
        """
        Add middleware to all services.

        Args:
             middlewares: List of middleware instances to apply.
        """
        for service in self._services.values():
            service.add_middleware(middlewares)
