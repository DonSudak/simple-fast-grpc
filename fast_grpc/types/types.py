from typing import (
    Awaitable,
    Callable,
    Generic,
    TypeVar,
    Sequence,
    AsyncIterable,
)

from pydantic import conint, BaseModel

from fast_grpc.core.context import ControllerContext

Request = TypeVar("Request")
"""Type variable representing the request type."""

Response = TypeVar("Response")
"""Type variable representing the response type."""

Method = Callable[
    [Request, ControllerContext], AsyncIterable[Response] | Awaitable[Response]
]
"""Type alias for a method callable accepting a request and context, returning a response."""

MetadataType = Sequence[tuple[str, str | bytes]]
"""Type alias for metadata as a sequence of key-value tuples."""

Uint32 = conint(ge=0, lt=2**32)
"""Unsigned 32-bit integer constrained type (0 to 2^32 - 1)."""

Uint64 = conint(ge=0, lt=2**64)
"""Unsigned 64-bit integer constrained type (0 to 2^64 - 1)."""

Int32 = conint(ge=-(2**31), lt=2**31)
"""Signed 32-bit integer constrained type (-2^31 to 2^31 - 1)."""

Int64 = conint(ge=-(2**63), lt=2**63)
"""Signed 64-bit integer constrained type (-2^63 to 2^63 - 1)."""

Double = float
"""Alias for double-precision floating-point type."""

T = TypeVar("T", bytes, int, str, bool, float)
"""Type variable constrained to basic proto-compatible types."""


class WrapperValue(BaseModel, Generic[T]):
    """Generic wrapper for scalar values in proto messages."""

    value: T
    """The wrapped scalar value."""


DoubleValue = WrapperValue[Double] | None
"""Optional wrapper for double-precision float values."""

FloatValue = WrapperValue[float] | None
"""Optional wrapper for single-precision float values."""

Int64Value = WrapperValue[Int64] | None
"""Optional wrapper for 64-bit signed integer values."""

UInt64Value = WrapperValue[Uint64] | None
"""Optional wrapper for 64-bit unsigned integer values."""

Int32Value = WrapperValue[Int32] | None
"""Optional wrapper for 32-bit signed integer values."""

UInt32Value = WrapperValue[Uint32] | None
"""Optional wrapper for 32-bit unsigned integer values."""

BoolValue = WrapperValue[bool] | None
"""Optional wrapper for boolean values."""

StringValue = WrapperValue[str] | None
"""Optional wrapper for string values."""

BytesValue = WrapperValue[bytes] | None
"""Optional wrapper for bytes values."""


class Empty(BaseModel):
    """Empty message type for proto definitions with no fields."""
    ...