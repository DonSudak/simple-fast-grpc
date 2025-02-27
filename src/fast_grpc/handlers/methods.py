import inspect
from abc import ABC
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Callable,
    Dict,
    Optional,
    Type,
    Union,
)

from google.protobuf.message import Message
from pydantic import BaseModel

from fast_grpc.core.context import ControllerContext
from fast_grpc.core.dependencies import Dependencies
from logzero import logger
from fast_grpc.schema.utils import (
    get_param_annotation_model,
    get_typed_signature,
    to_pascal_case,
)
from fast_grpc.utils.helpers import (
    dict_to_message,
    json_to_message,
    message_to_dict,
    message_to_str,
)


class MethodMode(Enum):
    """Enumeration of supported gRPC method modes.

    Defines the possible combinations of request and response types (unary or streaming).
    """

    UNARY_UNARY = "unary_unary"  # Single request, single response
    UNARY_STREAM = "unary_stream"  # Single request, streaming response
    STREAM_UNARY = "stream_unary"  # Streaming request, single response
    STREAM_STREAM = "stream_stream"  # Streaming request, streaming response


class BaseMethod(ABC):
    """
    Abstract base class for gRPC method implementations.

    Provides common functionality for handling requests, responses, and dependencies.
    """

    mode: MethodMode

    def __init__(
        self,
        endpoint: Callable,
        *,
        name: Optional[str] = None,
        request_model: Optional[Type[BaseModel]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        description: str = "",
    ) -> None:
        """
        Initialize a gRPC method.

        Args:
            endpoint: The callable function to execute for this method.
            name: Optional custom name for the method (default: None, derived from endpoint).
            request_model: Pydantic model for validating requests (default: None).
            response_model: Pydantic model for validating responses (default: None).
            description: Description of the method's purpose (default: "").

        Raises:
            ValueError: If response_model is provided but does not subclass BaseModel.
        """
        self.name = name or to_pascal_case(endpoint.__name__)
        self.dependencies = Dependencies(endpoint)
        self.endpoint = self.dependencies.get_close_dependencies_wrapped_endpoint(
            endpoint
        )
        self.request_model = request_model
        self.response_model = response_model
        self.description = description
        endpoint_signature = get_typed_signature(self.endpoint)
        request, *keys = endpoint_signature.parameters.keys()
        self.request_param = endpoint_signature.parameters[request]
        self.context_param = endpoint_signature.parameters[keys[0]] if keys else None
        if self.request_param.annotation is not inspect.Signature.empty:
            request_param_model = get_param_annotation_model(
                self.request_param.annotation, self.is_request_iterable
            )
            self.request_model = self.request_model or request_param_model
        if endpoint_signature.return_annotation is not inspect.Signature.empty:
            response_param_model = get_param_annotation_model(
                endpoint_signature.return_annotation, self.is_response_iterable
            )
            self.response_model = self.response_model or response_param_model
        if self.response_model and not issubclass(self.response_model, BaseModel):
            raise ValueError("response_model must be a BaseModel subclass")
        if self.response_model and not issubclass(self.response_model, BaseModel):
            raise ValueError("response_model must be a BaseModel subclass")

    @property
    def is_request_iterable(self) -> bool:
        """
        Check if the method accepts a streaming request.

        Returns:
            bool: True if the mode is STREAM_UNARY or STREAM_STREAM, False otherwise.
        """
        return self.mode in (MethodMode.STREAM_UNARY, MethodMode.STREAM_STREAM)

    @property
    def is_response_iterable(self) -> bool:
        """
        Check if the method produces a streaming response.

        Returns:
            bool: True if the mode is UNARY_STREAM or STREAM_STREAM, False otherwise.
        """
        return self.mode in (MethodMode.UNARY_STREAM, MethodMode.STREAM_STREAM)

    def solve_params(self, request: Any, context: ControllerContext) -> Dict[str, Any]:
        """
        Resolve and validate parameters for the endpoint call.

        Args:
            request: The incoming request data (single or iterable).
            context: The controller context providing execution details.

        Returns:
            Dict[str, Any]: Dictionary of resolved parameter values.
        """
        values: Dict[str, Any] = {}
        if self.context_param:
            values[self.context_param.name] = context

        if not self.request_model:
            values[self.request_param.name] = request
            return values
        if isinstance(request, AsyncIterator):

            async def validate_async_iterator_request() -> AsyncGenerator[Any, None]:
                async for item in request:
                    yield self.request_model.model_validate(message_to_dict(item))

            values[self.request_param.name] = validate_async_iterator_request()
        else:
            values[self.request_param.name] = self.request_model.model_validate(
                message_to_dict(request)
            )
        return values

    def serialize_response(self, response: Any, context: ControllerContext) -> Any:
        """
        Serialize the endpoint response into the expected format.

        Args:
            response: The raw response from the endpoint.
            context: The controller context providing output type information.

        Returns:
            Any: The serialized response compatible with gRPC.
        """
        if isinstance(response, context.output_type):
            return response

        if self.response_model:
            validated_response = self.response_model.model_validate(response)
            return json_to_message(
                validated_response.model_dump_json(),
                context.output_type,
            )
        if isinstance(response, dict):
            return dict_to_message(response, context.output_type)
        return response


class UnaryUnaryMethod(BaseMethod):
    """Implementation of a unary-unary gRPC method (single request, single response)."""

    mode = MethodMode.UNARY_UNARY

    async def __call__(
        self,
        request: Union[Message, AsyncIterable[Message]],
        context: ControllerContext,
        dependencies_results: Dict[str, Any],
        *args,
        **kwargs,
    ) -> Message:
        """
        Execute the unary-unary method.

        Args:
            request: The incoming request (single message or iterable).
            context: The controller context for execution details.
            dependencies_results: Resolved dependency values.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Message: The serialized response message.
        """
        values = self.solve_params(request, context)
        values |= dependencies_results
        result = await self.endpoint(**values)
        response = self.serialize_response(result, context)
        logger.info(
            f"GRPC invoke {context.controller_method.name}({message_to_str(request)}) "
            f"[OK] {context.elapsed_time} ms"
        )
        return response


class StreamUnaryMethod(UnaryUnaryMethod):
    """Implementation of a stream-unary gRPC method (streaming request, single response)."""

    mode = MethodMode.STREAM_UNARY


class UnaryStreamMethod(BaseMethod):
    """Implementation of a unary-stream gRPC method (single request, streaming response)."""

    mode = MethodMode.UNARY_STREAM

    async def __call__(
        self,
        request: Union[Message, AsyncIterable[Message]],
        context: ControllerContext,
        dependencies_results: Dict[str, Any],
        *args,
        **kwargs,
    ) -> AsyncGenerator[Message, None]:
        """
        Execute the unary-stream method.

        Args:
            request: The incoming request (single message or iterable).
            context: The controller context for execution details.
            dependencies_results: Resolved dependency values.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Yields:
            Message: Serialized response messages one at a time.
        """
        values = self.solve_params(request, context)
        values |= dependencies_results
        iterator_response = self.endpoint(**values)
        async for response in iterator_response:
            yield self.serialize_response(response, context)
        logger.info(
            f"GRPC invoke {context.controller_method.name}({message_to_str(request)}) "
            f"[OK] {context.elapsed_time} ms"
        )


class StreamStreamMethod(UnaryStreamMethod):
    """Implementation of a stream-stream gRPC method (streaming request, streaming response)."""

    mode = MethodMode.STREAM_STREAM


IterableMethodType = Union[UnaryStreamMethod, StreamStreamMethod]
"""Type alias for methods with iterable responses."""

NotIterableMethodType = Union[UnaryUnaryMethod, StreamUnaryMethod]
"""Type alias for methods with non-iterable responses."""

MethodType = Union[IterableMethodType, NotIterableMethodType]
"""Type alias for all supported method types."""
