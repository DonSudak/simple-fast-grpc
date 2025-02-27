import asyncio
import contextvars
import functools
import importlib.util
import inspect
import re
from typing import Any, Callable, get_origin, get_args, AsyncIterable

from pydantic._internal._typing_extra import eval_type_lenient


def is_camel_case(name: str) -> bool:
    """Check if a string follows CamelCase convention."""
    return re.match(r"^(?:[A-Z][a-z]+)*$", name) is not None


def is_snake_case(name: str) -> bool:
    """Verify if a string adheres to snake_case format."""
    if not name:
        return False
    if name[0] == "_" or name[-1] == "_":
        return False
    if any(c.isupper() for c in name):
        return False
    if "__" in name:
        return False
    if not all(c.isalnum() or c == "_" for c in name):
        return False
    if "_" not in name:
        return False
    return True


def camel_to_snake(name: str) -> str:
    """
    Replace uppercase letters with _+lowercase letters, for example "FastGRPC" -> "fast_grpc"
    """
    snake_case_str = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    if snake_case_str.startswith("_"):
        snake_case_str = snake_case_str[1:]
    return snake_case_str


def snake_to_camel(name: str) -> str:
    """
    Transform snake_case string to CamelCase.

    Example: "fast_grpc" becomes "FastGrpc".
    """
    return "".join(word.capitalize() for word in name.split("_"))


def await_sync_function(func: Callable) -> Callable:
    """Wrap a synchronous function to run asynchronously."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        context = contextvars.copy_context()
        args = (functools.partial(func, *args, **kwargs),)
        return await loop.run_in_executor(None, context.run, args)

    return wrapper


def load_model_from_file_location(name: str, path: str) -> Any:
    """Dynamically load a module from a file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_param_annotation_model(
    annotation: Any, is_streaming: bool = False
) -> Any | None:
    """Extract the model type from a parameter annotation."""
    if annotation is inspect.Signature.empty:
        return None
    if not is_streaming:
        return annotation
    origin_type = get_origin(annotation)
    args = get_args(annotation)
    if not issubclass(origin_type, AsyncIterable):
        return None
    return args[0] if args else None


def get_typed_annotation(annotation: Any, globals_dict: dict[str, Any]) -> Any:
    """Resolve type annotation to a concrete type."""
    if isinstance(annotation, str):
        from typing import ForwardRef

        annotation = ForwardRef(annotation)
        return eval_type_lenient(annotation, globals_dict, globals_dict)
    return annotation


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    """Generate a typed signature for a callable."""
    signature = inspect.signature(call)
    globals_dict = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globals_dict),
        )
        for param in signature.parameters.values()
    ]
    return_annotation = get_typed_annotation(signature.return_annotation, globals_dict)
    return inspect.Signature(typed_params, return_annotation=return_annotation)


def to_pascal_case(snake_str: str, delimiter: str = "_") -> str:
    """
    Convert snake_case string to PascalCase.

    Args:
        snake_str: Input string in snake_case.
        delimiter: Character separating words (default: "_").

    Returns:
        PascalCase version of the input string.
    """
    return "".join(word.capitalize() for word in snake_str.split(delimiter))
