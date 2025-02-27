import datetime
from enum import IntEnum
from pathlib import Path
from types import UnionType
from typing import Sequence, Any, Union

import grpc
from google.protobuf.descriptor import (
    ServiceDescriptor,
    Descriptor,
    FieldDescriptor,
    EnumDescriptor,
)
from jinja2 import Template
from pydantic import BaseModel
from typing_extensions import get_args, get_origin

from fast_grpc.core.controller import Controller
from fast_grpc.handlers.methods import MethodMode
from fast_grpc.utils import protoc_compile
from fast_grpc.types import Empty
from fast_grpc.types import (
    BoolValue,
    BytesValue,
    Double,
    DoubleValue,
    FloatValue,
    Int32,
    Int32Value,
    Int64,
    Int64Value,
    StringValue,
    Uint32,
    UInt32Value,
    Uint64,
    UInt64Value,
)

_base_types: dict[type, str] = {
    bytes: "bytes",
    # int
    int: "int32",
    float: "float",
    # Boolean
    bool: "bool",
    # Date and time
    datetime.datetime: "string",
    str: "string",
    Uint32: "uint32",
    Uint64: "uint64",
    Int32: "int32",
    Int64: "int64",
    Double: "double",
    Union: "oneof",
    UnionType: "oneof",
}
"""Mapping of Python types to their corresponding proto base types."""

_wrapper_types: dict[type, str] = {
    BoolValue: "google.protobuf.BoolValue",
    BytesValue: "google.protobuf.BytesValue",
    DoubleValue: "google.protobuf.DoubleValue",
    FloatValue: "google.protobuf.FloatValue",
    Int32Value: "google.protobuf.Int32Value",
    Int64Value: "google.protobuf.Int64Value",
    StringValue: "google.protobuf.StringValue",
    UInt32Value: "google.protobuf.UInt32Value",
    UInt64Value: "google.protobuf.UInt64Value",
}
"""Mapping of wrapper types to their proto equivalents."""

# 定义 Jinja2 模板
PROTO_TEMPLATE = """
syntax = "proto3";

package {{ proto_define.package }};

{% for service in proto_define.services %}
service {{ service.name }} {
    {% for method in service.methods -%}
    rpc {{ method.name }}({{ method.request }}) returns ({{ method.response }});
    {%- if not loop.last %}
    {% endif %}
    {%- endfor %}
}
{% endfor %}
{% for enum in proto_define.enums.values() %}
enum {{ enum.name }} {
    {% for field in enum.fields -%}
    {{ field.name }} = {{ field.index }};
    {%- if not loop.last %}
    {% endif %}
    {%- endfor %}
}
{% endfor %}
{% for message in proto_define.messages.values() %}
message {{ message.name }} {
    {% for field in message.fields -%}
    {{ field.type }} {{ field.name }} = {{ field.index }};
    {%- if not loop.last %}
    {% endif %}
    {%- endfor %}
}
{% endfor %}
"""
"""Jinja2 template for generating proto files."""

PYTHON_TEMPLATE = """
import grpc
from enum import IntEnum
from pydantic import BaseModel
from fast_grpc.utils import message_to_pydantic, pydantic_to_message

pb2, pb2_grpc = grpc.protos_and_services("{{ proto_define.package }}")
{% for enum in proto_define.enums.values() %}
class {{ enum.name }}(IntEnum):
    {%- for field in enum.fields %}
    {{ field.name }} = {{ field.index }}
    {%- endfor %}

{% endfor %}
{% for message in proto_define.messages.values() %}
class {{ message.name }}(BaseModel):
    {%- if message.fields %}
    {%- for field in message.fields %}
    {{ field.name }}: {{ field.type }}
    {%- endfor %}
    {% else %}
    pass
    {% endif %}
{% endfor %}
{% for service in proto_define.services %}
class {{ service.name }}Client:
    def __init__(self, target: str="127.0.0.1:50051"):
        self.target = target

    {% for method in service.methods -%}
    def {{ method.name }}(self, request: {{ method.request }}) -> {{ method.response }}:
        with grpc.insecure_channel(self.target) as channel:
            client = pb2_grpc.{{ service.name }}Stub(channel)
            response = client.{{ method.name }}(pydantic_to_message(request, pb2.{{ method.request }}))
            return message_to_pydantic(response, {{ method.response }})

    {% endfor %}
{% endfor %}
"""
"""Jinja2 template for generating Python client code."""


class ProtoField(BaseModel):
    """Represents a field in a proto message or enum."""

    name: str
    index: int
    type: str = ""

    @property
    def proto_string(self) -> str:
        """
        Generate the proto string representation of the field.

        Returns:
            str: A string in the format '<type> <name> = <index>'.
        """
        return f"{self.type} {self.name} = {self.index}".strip()


class ProtoStruct(BaseModel):
    """Represents a proto message or enum structure."""

    name: str
    fields: list[ProtoField]


class ProtoMethod(BaseModel):
    """Represents a method in a proto service."""

    name: str
    request: str
    response: str
    mode: MethodMode = MethodMode.UNARY_UNARY
    client_streaming: bool = False
    server_streaming: bool = False


class ProtoService(BaseModel):
    """Represents a proto service definition."""

    name: str
    methods: list[ProtoMethod]


class ProtoDefine(BaseModel):
    """Represents the complete proto file definition."""

    package: str
    services: list[ProtoService]
    messages: dict[Any, ProtoStruct]
    enums: dict[Any, ProtoStruct]

    def render(self, proto_template: str) -> str:
        """
        Render the proto definition using a Jinja2 template.

        Args:
            proto_template: The Jinja2 template string to render.

        Returns:
            str: The rendered proto file content.
        """
        template = Template(proto_template)
        return template.render(proto_define=self)

    def render_proto_file(self) -> str:
        """
        Render the proto file content using the PROTO_TEMPLATE.

        Returns:
            str: The rendered proto file content.
        """
        return self.render(PROTO_TEMPLATE)

    def render_python_file(self) -> str:
        """
        Render the Python client code using the PYTHON_TEMPLATE.

        Returns:
            str: The rendered Python client code.
        """
        return self.render(PYTHON_TEMPLATE)


def generate_type_name(type_: type) -> str:
    """
    Generate a proto-compatible name for a generic type.

    Combines base name and type arguments into a single string.
    Examples: Response[User] -> UserResponse, Page[User] -> UserPage, NestedResponse[User, DataList] -> UserDataListNestedResponse

    Args:
        type_: The Python type to convert.

    Returns:
        str: The generated prototype name.

    Raises:
        ValueError: If the type is not a valid type or is unsupported.
    """
    if not isinstance(type_, type):
        raise ValueError(f"'{type_}' must be a type")
    origin = get_origin(type_)
    args = get_args(type_)
    if origin is None:
        if issubclass(type_, BaseModel):
            metadata = type_.__pydantic_generic_metadata__
            args = metadata["args"]
            origin = metadata["origin"] or type_
            type_names = [generate_type_name(t) for t in args]
            return "".join(type_names + [origin.__name__])
        if issubclass(type_, IntEnum):
            return type_.__name__
        if not issubclass(type_, tuple(_base_types)):
            raise ValueError(f"Unsupported type: {type_}")
        return type_.__name__.capitalize()
    else:
        if issubclass(origin, Sequence):
            return f"{generate_type_name(args[0])}List"
        if issubclass(origin, dict):
            return f"{generate_type_name(args[0])}{generate_type_name(args[1])}Dict"
        raise ValueError(f"Unsupported type: {type_}")


class ProtoBuilder:
    """Builder class for constructing proto definitions from services."""

    def __init__(self, package: str) -> None:
        """
        Initialize the ProtoBuilder with a package name.

        Args:
            package: The package name for the proto definition.
        """
        self._proto_define = ProtoDefine(
            package=package, services=[], messages={}, enums={}
        )

    def add_service(self, service: Controller) -> "ProtoBuilder":
        """
        Add a service to the proto definition.

        Args:
            service: The Service instance to add.

        Returns:
            ProtoBuilder: Self, for method chaining.
        """
        srv = ProtoService(name=service.name, methods=[])
        self._proto_define.services.append(srv)
        for name, method in service.methods.items():
            request = self.convert_message(method.request_model or Empty)
            response = self.convert_message(method.response_model or Empty)
            proto_method = ProtoMethod(
                name=name, request=request.name, response=response.name
            )
            if method.mode in {MethodMode.STREAM_UNARY, MethodMode.STREAM_STREAM}:
                proto_method.request = f"stream {proto_method.request}"
            if method.mode in {MethodMode.UNARY_STREAM, MethodMode.STREAM_STREAM}:
                proto_method.response = f"stream {proto_method.response}"
            srv.methods.append(proto_method)
        return self

    def get_proto(self) -> ProtoDefine:
        """
        Get the constructed proto definition.

        Returns:
            ProtoDefine: The complete proto definition object.
        """
        return self._proto_define

    def convert_message(self, schema: type[BaseModel]) -> ProtoStruct:
        """
        Convert a Pydantic model to a proto message structure.

        Args:
            schema: The Pydantic model to convert.

        Returns:
            ProtoStruct: The corresponding proto message structure.
        """
        if schema in self._proto_define.messages:
            return self._proto_define.messages[schema]
        message = ProtoStruct(name=generate_type_name(schema), fields=[])
        for i, (name, field) in enumerate(schema.model_fields.items(), 1):
            type_name = self._get_type_name(field.annotation)
            message.fields.append(ProtoField(name=name, type=type_name, index=i))
        self._proto_define.messages[schema] = message
        return message

    def convert_enum(self, schema: type[IntEnum]) -> ProtoStruct:
        """
        Convert an IntEnum to a proto enum structure.

        Args:
            schema: The IntEnum to convert.

        Returns:
            ProtoStruct: The corresponding proto enum structure.
        """
        if schema in self._proto_define.enums:
            return self._proto_define.enums[schema]
        enum_struct = ProtoStruct(
            name=schema.__name__,
            fields=[
                ProtoField(name=member.name, index=member.value) for member in schema
            ],
        )
        self._proto_define.enums[schema] = enum_struct
        return enum_struct

    def _get_type_name(self, type_: type) -> str:
        """
        Get the proto type name for a given Python type.

        Args:
            type_: The Python type to convert.

        Returns:
            str: The proto-compatible type name.

        Raises:
            ValueError: If the type is unsupported.
        """
        origin = get_origin(type_)
        args = get_args(type_)
        if origin is None:
            if issubclass(type_, BaseModel):
                message = self.convert_message(type_)
                return message.name
            if issubclass(type_, IntEnum):
                struct = self.convert_enum(type_)
                return struct.name
            if not issubclass(type_, tuple(_base_types)):
                raise ValueError(f"Unsupported type: {type_}")
            return _base_types[type_]

        elif origin in (Union, UnionType) and type(None) in args:
            if issubclass(args[0], BaseModel):
                message = self.convert_message(args[0])
                return message.name
            if issubclass(args[0], IntEnum):
                struct = self.convert_enum(args[0])
                return struct.name
            if not issubclass(args[0], tuple(_base_types)):
                raise ValueError(f"Unsupported type: {type_}")
            return _base_types[args[0]]
        else:
            if issubclass(origin, Sequence):
                return f"repeated {self._get_type_name(args[0])}"
            if issubclass(origin, dict):
                return f"map <{self._get_type_name(args[0])}, {self._get_type_name(args[1])}>"
            raise ValueError(f"Unsupported type: {type_}")


class ClientBuilder:
    """Builder class for constructing client-side proto definitions from descriptors."""

    def __init__(self, package: str) -> None:
        """
        Initialize the ClientBuilder with a package name.

        Args:
            package: The package name for the proto definition.
        """
        self._proto_define = ProtoDefine(
            package=package, services=[], messages={}, enums={}
        )
        self.pb2 = grpc.protos(self._proto_define.package)
        self._proto_package = self.pb2.DESCRIPTOR.package

    def get_proto(self) -> ProtoDefine:
        """
        Get the constructed proto definition from descriptors.

        Returns:
            ProtoDefine: The complete proto definition object.
        """
        for service in self.pb2.DESCRIPTOR.services_by_name.values():
            self.add_service(service)
        return self._proto_define

    def add_service(self, service: ServiceDescriptor) -> "ClientBuilder":
        """
        Add a service to the proto definition from a descriptor.

        Args:
            service: The ServiceDescriptor to add.

        Returns:
            ClientBuilder: Self, for method chaining.
        """
        srv = ProtoService(name=service.name, methods=[])
        self._proto_define.services.append(srv)
        for name, method in service.methods_by_name.items():
            request = self.convert_message(method.input_type)
            response = self.convert_message(method.output_type)
            proto_method = ProtoMethod(
                name=name,
                request=request.name,
                response=response.name,
                client_streaming=method.client_streaming,
                server_streaming=method.server_streaming,
            )
            if method.client_streaming and method.server_streaming:
                proto_method.mode = MethodMode.STREAM_STREAM
            elif method.client_streaming:
                proto_method.mode = MethodMode.STREAM_UNARY
            elif method.server_streaming:
                proto_method.mode = MethodMode.UNARY_STREAM
            else:
                proto_method.mode = MethodMode.UNARY_UNARY
            srv.methods.append(proto_method)
        return self

    def _gen_class_name(self, name: str) -> str:
        """
        Generate a class name from a fully qualified proto name.

        Args:
            name: The fully qualified proto name.

        Returns:
            str: A simplified class name with underscores instead of dots.
        """
        return "_".join(name.removeprefix(f"{self._proto_package}.").split("."))

    def convert_message(self, message: Descriptor) -> ProtoStruct:
        """
        Convert a proto message descriptor to a ProtoStruct.

        Args:
            message: The Descriptor of the proto message.

        Returns:
            ProtoStruct: The corresponding proto message structure.
        """
        if message in self._proto_define.messages:
            return self._proto_define.messages[message]
        name = self._gen_class_name(message.full_name)
        schema = ProtoStruct(name=name, fields=[])
        for i, field in enumerate(message.fields):
            type_name = self._get_type_name(field)
            schema.fields.append(ProtoField(name=field.name, type=type_name, index=i))
        self._proto_define.messages[message] = schema
        return schema

    def convert_enum(self, enum_meta: EnumDescriptor) -> ProtoStruct:
        """
        Convert a proto enum descriptor to a ProtoStruct.

        Args:
            enum_meta: The EnumDescriptor of the proto enum.

        Returns:
            ProtoStruct: The corresponding proto enum structure.
        """
        if enum_meta in self._proto_define.enums:
            return self._proto_define.enums[enum_meta]
        name = self._gen_class_name(enum_meta.full_name)
        enum_struct = ProtoStruct(
            name=name,
            fields=[
                ProtoField(name=name, index=value.index)
                for name, value in enum_meta.values_by_name.items()
            ],
        )
        self._proto_define.enums[enum_meta] = enum_struct
        return enum_struct

    def _get_type_name(self, field: FieldDescriptor) -> str:
        """
        Get the proto type name for a field descriptor.

        Args:
            field: The FieldDescriptor to convert.

        Returns:
            str: The proto-compatible type name.

        Raises:
            ValueError: If the field type is unsupported.
        """
        if field.message_type and field.message_type.GetOptions().map_entry:
            key_type = self._get_type_name(field.message_type.fields_by_name["key"])
            value_type = self._get_type_name(field.message_type.fields_by_name["value"])
            return f"dict[{key_type}, {value_type}]"

        def get_base_type() -> str:
            if field.type == FieldDescriptor.TYPE_MESSAGE:
                message = self.convert_message(field.message_type)
                return message.name
            elif field.type == FieldDescriptor.TYPE_ENUM:
                struct = self.convert_enum(field.enum_type)
                return struct.name

            type_map = {
                FieldDescriptor.TYPE_DOUBLE: "float",
                FieldDescriptor.TYPE_FLOAT: "float",
                FieldDescriptor.TYPE_INT64: "int",
                FieldDescriptor.TYPE_UINT64: "int",
                FieldDescriptor.TYPE_INT32: "int",
                FieldDescriptor.TYPE_FIXED64: "int",
                FieldDescriptor.TYPE_FIXED32: "int",
                FieldDescriptor.TYPE_UINT32: "int",
                FieldDescriptor.TYPE_SFIXED32: "int",
                FieldDescriptor.TYPE_SFIXED64: "int",
                FieldDescriptor.TYPE_SINT32: "int",
                FieldDescriptor.TYPE_SINT64: "int",
                FieldDescriptor.TYPE_BOOL: "bool",
                FieldDescriptor.TYPE_STRING: "str",
                FieldDescriptor.TYPE_BYTES: "bytes",
            }

            if field.type in type_map:
                return type_map[field.type]

            raise ValueError(f"Unsupported field type: {field.type}")

        base_type = get_base_type()
        if field.label == FieldDescriptor.LABEL_REPEATED:
            return f"list[{base_type}]"
        return base_type


def proto_to_python_client(proto_path: str) -> str:
    """
    Generate Python client code from a proto file.

    Compiles the proto file and builds a client-side proto definition.

    Args:
        proto_path: The path to the proto file.

    Returns:
        str: The generated Python client code.
    """
    protoc_compile(Path(proto_path))
    builder = ClientBuilder(proto_path)
    proto_define = builder.get_proto()
    return proto_define.render_python_file()
