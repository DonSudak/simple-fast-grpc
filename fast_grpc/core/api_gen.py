from enum import Enum
from pathlib import Path
from typing import Any, Callable, AsyncGenerator

import grpc
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from grpc.aio import AioRpcError
from pydantic import create_model, BaseModel

from fast_grpc.handlers import MethodMode
from fast_grpc.schema import snake_to_camel, camel_to_snake
from fast_grpc.schema.proto import (
    ProtoDefine,
    ClientBuilder,
    ProtoService,
    ProtoMethod,
)
from fast_grpc.types import (
    Int32,
    Empty,
)
from fast_grpc.utils import message_to_dict


class ConnectionInterface(BaseModel):
    """Interface for holding gRPC client and proto objects."""

    conn: Any
    protos: Any


class GRPCConnection:
    """Mock class for gRPC connection dependency."""

    def __init__(self, address: str, controller_name: str, proto_path: str):
        self.address = address
        self.controller_name = controller_name
        self.proto_path = proto_path

    async def __call__(self) -> AsyncGenerator[ConnectionInterface, None]:
        async with grpc.aio.insecure_channel(self.address) as channel:
            protos, services = grpc.protos_and_services(  # type: ignore
                f"{self.proto_path}{self.controller_name}.proto"
            )
            stub_name = f"{self.controller_name}Stub"
            stub = services.__dict__.get(stub_name, None)
            if stub is None:
                raise Exception(
                    f"No stub class with name: {stub_name} in {self.controller_name}_pb2_grpc.py"
                )

            yield ConnectionInterface(conn=stub(channel), protos=protos)


class ApiGenerator:
    """Generator for creating a FastAPI test application from proto files."""

    def __init__(self, proto_path: str, address: str = "127.0.0.1:50051") -> None:
        """Initialize the API generator with a proto file directory path.

        Args:
            proto_path: Path to the directory containing proto files to parse.
        """
        self.proto_path = proto_path
        self.address = address
        self.app = FastAPI(
            title="Test API from Proto",
            description="Generated test API from proto files",
        )
        self.models: dict[str, type[BaseModel] | type[str]] = {}
        self._type_mapping = {
            "int": Int32,
            "float": float,
            "bool": bool,
            "str": str,
            "bytes": bytes,
        }

    def str_to_type(self, type_str: str) -> type:
        """
            Converts a type string into a type object, supporting models, lists, dictionaries, and tuples.

        Args:
            type_str: A string representing a type (e.g., "int", "list[int]", "dict[str, TestModel]", "tuple[int]").

        Returns:
            Type: The resulting type object (e.g., int, List[int], Dict[str, TestModel], Tuple[int]).

        Raises:
            ValueError: If the type is not found or not supported.
        """
        # If not [ it is simple type or name of model
        if "[" not in type_str:
            if type_str in self.models:
                return self.models[type_str]
            if type_str in self._type_mapping:
                return self._type_mapping[type_str]
            raise ValueError(f"Unknown type or model: {type_str}")

        # Splitting type and args
        container_name = type_str[: type_str.index("[")]
        args_str = type_str[type_str.index("[") + 1 : type_str.rindex("]")]

        # Available types
        container_types = {
            "list": list,
            "dict": dict,
            "tuple": tuple,
        }

        if container_name not in container_types:
            raise ValueError(f"Unsupported container type: {container_name}")

        container_type = container_types[container_name]

        # Parsing args
        if container_name == "list":
            arg_type = self.str_to_type(args_str)
            return container_type[arg_type]

        if container_name == "dict":
            key_str, value_str = args_str.split(",", 1)  # Splitting on key and value
            key_type = self.str_to_type(key_str.strip())
            value_type = self.str_to_type(value_str.strip())
            return container_type[key_type, value_type]

        if container_name == "tuple":
            arg_type = self.str_to_type(args_str)
            return container_type[arg_type]

        raise Exception("No type found")

    def _create_basemodel(self, name: str, fields: list[Any]) -> type[BaseModel]:
        """
        Create a Pydantic BaseModel from proto fields.

        Args:
            name: The name of the proto message or enum (as a string).
            fields: List of ProtoField objects defining the message structure.

        Returns:
            Type[BaseModel]: The generated Pydantic model class.
        """
        model_fields = {}
        for field in fields:
            field_type = self.str_to_type(field.type)
            model_fields[field.name] = (field_type, None)
        model = create_model(snake_to_camel(name), **model_fields)
        return model

    def _generate_models(self, proto: ProtoDefine) -> None:
        """
        Generate Pydantic BaseModels for all messages and enums in the proto definition.

        Args:
            proto: The ProtoDefine object containing messages and enums.
        """
        for _, struct in proto.messages.items():
            self.models[struct.name] = self._create_basemodel(
                struct.name, struct.fields
            )
        for _, struct in proto.enums.items():
            self.models[struct.name] = str

    def get_endpoint(
        self,
        request_model: type[BaseModel] | type[str],
        response_model: type[BaseModel] | type[str],
        method: ProtoMethod,
        grpc_conn: GRPCConnection,
    ):
        """
        Generate a FastAPI endpoint based on the proto method type.

        Args:
            request_model: Pydantic model or type for the request.
            response_model: Pydantic model or type for the response.
            method: ProtoMethod object defining the gRPC method.
            grpc_conn: GRPCConnection instance for dependency injection.

        Returns:
            Callable: The generated FastAPI endpoint function.
        """

        async def unary_unary_endpoint(
            request: request_model,  # type: ignore
            connection: ConnectionInterface = Depends(grpc_conn),
        ) -> response_model:  # type: ignore
            """
            Call a unary-unary gRPC method and return the response.

            Args:
                request: The request data matching the proto method's request model.
                connection: The gRPC connection interface (injected via Depends).

            Returns:
                response_model: The response from the gRPC controller.

            Raises:
                HTTPException: If a gRPC error occurs, with status code 422.
            """
            try:
                grpc_request = getattr(connection.protos, method.request)(
                    **request.model_dump(exclude_unset=True)
                )
                response = await getattr(connection.conn, method.name)(grpc_request)
                return response_model(**message_to_dict(response))
            except AioRpcError as e:
                raise HTTPException(status_code=422, detail=str(e))

        async def stream_unary_endpoint(
            request: list[request_model],  # type: ignore
            connection: ConnectionInterface = Depends(grpc_conn),
        ) -> response_model:  # type: ignore
            """
            Call a stream-unary gRPC method and return the response.

            Args:
                request: List of request data matching the proto method's request model.
                connection: The gRPC connection interface (injected via Depends).

            Returns:
                response_model: The response from the gRPC controller.

            Raises:
                HTTPException: If a gRPC error occurs, with status code 422.
            """
            try:

                async def data_generator():
                    for req in request:
                        yield getattr(connection.protos, method.request)(
                            **req.model_dump(exclude_unset=True)
                        )

                response = await getattr(connection.conn, method.name)(data_generator())
                return response_model(**message_to_dict(response))

            except AioRpcError as e:
                raise HTTPException(status_code=422, detail=str(e))

        async def unary_stream_endpoint(
            request: request_model, connection: ConnectionInterface = Depends(grpc_conn)  # type: ignore
        ) -> list[response_model]:  # type: ignore
            """
            Call a unary-stream gRPC method and return a list of responses.

            Args:
                request: The request data matching the proto method's request model.
                connection: The gRPC connection interface (injected via Depends).

            Returns:
                List[response_model]: List of responses from the gRPC controller.

            Raises:
                HTTPException: If a gRPC error occurs, with status code 422.
            """
            try:
                grpc_request = getattr(connection.protos, method.request)(
                    **request.model_dump(exclude_unset=True)
                )
                responses = []
                async for grpc_response in getattr(connection.conn, method.name)(
                    grpc_request
                ):
                    responses.append(response_model(**message_to_dict(grpc_response)))
                return responses
            except AioRpcError as e:
                raise HTTPException(status_code=422, detail=str(e))

        async def stream_stream_endpoint(
            request: list[request_model],  # type: ignore
            connection: ConnectionInterface = Depends(grpc_conn),
        ) -> list[response_model]:  # type: ignore
            """
            Call a stream-stream gRPC method and return a list of responses.

            Args:
                request: List of request data matching the proto method's request model.
                connection: The gRPC connection interface (injected via Depends).

            Returns:
                List[response_model]: List of responses from the gRPC controller.

            Raises:
                HTTPException: If a gRPC error occurs, with status code 422.
            """
            try:

                async def data_generator():
                    for req in request:
                        yield getattr(connection.protos, method.request)(
                            **req.model_dump(exclude_unset=True)
                        )

                responses = []
                async for grpc_response in getattr(connection.conn, method.name)(
                    data_generator()
                ):
                    responses.append(response_model(**message_to_dict(grpc_response)))
                return responses
            except AioRpcError as e:
                raise HTTPException(status_code=422, detail=str(e))

        endpoints: dict[Enum, Callable] = {
            MethodMode.UNARY_UNARY: unary_unary_endpoint,
            MethodMode.STREAM_UNARY: stream_unary_endpoint,
            MethodMode.UNARY_STREAM: unary_stream_endpoint,
            MethodMode.STREAM_STREAM: stream_stream_endpoint,
        }
        return endpoints[method.mode]

    def _register_endpoints(
        self, router: APIRouter, methods: list, grpc_conn: GRPCConnection
    ) -> None:
        for method in methods:
            request_model = self.models.get(method.request, Empty)
            response_model = self.models.get(method.response, Empty)

            endpoint: Callable = self.get_endpoint(
                request_model=request_model,
                response_model=response_model,
                method=method,
                grpc_conn=grpc_conn,
            )

            router.add_api_route(
                path=f"/{camel_to_snake(method.name)}",
                endpoint=endpoint,
                methods=["get"] if isinstance(request_model, Empty) else ["post"],
            )

    def _gen_router(self, service: ProtoService) -> APIRouter:
        grpc_conn = GRPCConnection(self.address, service.name, self.proto_path)
        router = APIRouter(prefix=f"/{service.name}", tags=[service.name])
        self._register_endpoints(router, service.methods, grpc_conn)
        return router

    def generate_api(self) -> FastAPI:
        """Generate a FastAPI test application from proto files in the directory.

        Iterates over all .proto files, generates models and endpoints, and prepares the API.

        Returns:
            FastAPI: The generated FastAPI application with Swagger documentation.
        """

        for proto in Path(self.proto_path).iterdir():
            if str(proto).endswith(".proto"):
                builder = ClientBuilder(str(proto))
                proto_ = builder.get_proto()
                self._generate_models(proto_)
                for service in proto_.services:
                    self.app.include_router(self._gen_router(service))

        return self.app
