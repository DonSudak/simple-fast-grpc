import time

import grpc
from grpc.aio import Metadata, ServicerContext
from typing import Sequence, Union


class ControllerContext:
    """
    Context manager for handling controller execution details.

    This class encapsulates the gRPC context, method, and descriptor, providing
    utilities to track execution time, metadata, and manage the request lifecycle.
    """

    def __init__(
        self, grpc_context: ServicerContext, method: any, method_descriptor: any
    ) -> None:
        """
        Initialize the ServiceContext with gRPC details.

        Args:
            grpc_context: The underlying gRPC ServicerContext object.
            method: The method being executed within this context.
            method_descriptor: Descriptor of the method, containing input/output types.
        """
        self.grpc_context = grpc_context
        self.controller_method = method
        self.method_descriptor = method_descriptor
        self.input_type = method_descriptor.input_type._concrete_class
        self.output_type = method_descriptor.output_type._concrete_class
        self._start_time = time.time()
        self._metadata = {}

    @property
    def elapsed_time(self) -> int:
        """
        Calculate the time elapsed since context initialization in milliseconds.

        Returns:
            int: Elapsed time in milliseconds.
        """
        return int(time.time() - self._start_time) * 1000

    @property
    def metadata(self) -> dict[str, str]:
        """
        Retrieve metadata associated with the request.

        Lazily loads metadata from the gRPC context if not already cached.

        Returns:
            dict[str, str]: A dictionary of metadata key-value pairs.
        """
        if not self._metadata:
            self._metadata = dict(self.grpc_context.invocation_metadata())  # type: ignore
        return self._metadata  # type: ignore

    def time_remaining(self) -> float:
        """
        Get the remaining time before the request deadline.

        Returns:
            float: Remaining time in seconds.
        """
        return self.grpc_context.time_remaining()

    def invocation_metadata_(
        self,
    ) -> Union[Metadata, Sequence[tuple[str, Union[str, bytes]]], None]:
        """
        Fetch the invocation metadata provided by the client.

        Returns:
            Union[Metadata, Sequence[tuple[str, Union[str, bytes]]], None]:
                The metadata as a Metadata object, sequence of tuples, or None if not available.
        """
        return self.grpc_context.invocation_metadata()

    def peer(self) -> str:
        """
        Obtain the identity of the calling peer.

        Returns:
            str: A string identifying the peer (e.g., IP address or hostname).
        """
        return self.grpc_context.peer()

    async def abort(self, code: grpc.StatusCode, details: str) -> None:
        """
        Abort the current request with a specific status code and message.

        Args:
            code: The gRPC status code indicating the reason for abortion.
            details: A human-readable description of the error.

        Returns:
            None
        """
        await self.grpc_context.abort(code, details)

    def set_code(self, code: grpc.StatusCode) -> None:
        """
        Set the status code for the response.

        Args:
            code: The gRPC status code to set.

        Returns:
            None
        """
        self.grpc_context.set_code(code)

    def set_details(self, details: str) -> None:
        """
        Set the details message for the response.

        Args:
            details: A string describing the response status.

        Returns:
            None
        """
        self.grpc_context.set_details(details)
