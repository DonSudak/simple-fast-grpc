import grpc


class GRPCException(Exception):
    """
    Custom exception for gRPC-related errors.

    This exception encapsulates a gRPC status code and detailed message,
    allowing for precise error handling in gRPC controllers.
    """

    def __init__(self, status: grpc.StatusCode, details: str) -> None:
        """
        Initialize the GRPCException with a status code and details.

        Args:
            status: The gRPC status code indicating the error type.
            details: A human-readable description of the error.

        Attributes:
            status (grpc.StatusCode): The gRPC status code.
            details (str): Detailed error message.
        """
        self.status = status
        self.details = details
        super().__init__(f"{status.name}: {details}")
