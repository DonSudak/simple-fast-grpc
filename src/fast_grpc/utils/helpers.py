import importlib.util
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import (
    AsyncIterator,
    Sequence,
    Any,
)

from google.protobuf.json_format import MessageToDict, Parse, ParseDict
from google.protobuf.text_format import MessageToString
from logzero import logger
from pydantic import BaseModel


def import_string(dotted_path: str) -> Any:
    """
    Import a module or class by its dotted path.

    Args:
        dotted_path: The dotted path string (e.g., 'module.submodule.ClassName').

    Returns:
        Any: The imported module or class.

    Raises:
        ImportError: If the path is invalid or the module/class cannot be found.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError(f"'{dotted_path}' doesn't look like a module path") from err

    module = import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(
            f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        ) from err


def get_project_root_path(mod_name: str) -> str:
    """
    Get the root directory path of a given module.

    Args:
        mod_name: The name of the module to inspect.

    Returns:
        str: The absolute path to the module's directory, or current working directory if not found.
    """
    mod = sys.modules.get(mod_name)
    if mod is not None and hasattr(mod, "__file__") and mod.__file__ is not None:
        return os.path.dirname(os.path.abspath(mod.__file__))
    return os.getcwd()


def load_model_from_file_location(name: str, path: str) -> Any:
    """
    Dynamically load a module from a file location.

    Args:
        name: The name to assign to the loaded module.
        path: The file path to the module.

    Returns:
        Any: The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    proto_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proto_module)
    return proto_module


def import_proto_file(proto_path: Path) -> tuple[Any, Any]:
    """
    Load generated Python modules from a proto file.

    Args:
        proto_path: The Path object pointing to the proto file.

    Returns:
        tuple[Any, Any]: A tuple containing the pb2 and pb2_grpc modules.

    Raises:
        FileNotFoundError: If the generated pb2 or pb2_grpc files do not exist.
    """
    base_name = proto_path.stem
    pb2_file_path = proto_path.parent / f"{base_name}_pb2.py"
    pb2_grpc_file_path = proto_path.parent / f"{base_name}_pb2_grpc.py"
    if not pb2_file_path.exists():
        raise FileNotFoundError(f"Generated pb2 file {pb2_file_path} not found")
    if not pb2_grpc_file_path.exists():
        raise FileNotFoundError(f"Generated pb2 file {pb2_grpc_file_path} not found")

    _pb2 = load_model_from_file_location(f"{base_name}_pb2.py", pb2_file_path)
    _pb2_grpc = load_model_from_file_location(
        f"{base_name}_pb2_grpc.py", pb2_grpc_file_path
    )
    return _pb2, _pb2_grpc


def message_to_dict(message: Any) -> dict[str, Any]:
    """
    Convert a proto message to a dictionary.

    Args:
        message: The proto message to convert.

    Returns:
        Dict[str, Any]: A dictionary representation of the message.
    """
    return MessageToDict(message, preserving_proto_field_name=True)


def json_to_message(data: str, message_cls: Any) -> Any:
    """
    Parse JSON data into a proto message.

    Args:
        data: The JSON string to parse.
        message_cls: The proto message class to instantiate.

    Returns:
        Any: The parsed proto message instance.
    """
    return Parse(data, message_cls(), ignore_unknown_fields=True)


def dict_to_message(data: dict[str, Any], message_cls: Any) -> Any:
    """
    Convert a dictionary to a proto message.

    Args:
        data: The dictionary to convert.
        message_cls: The proto message class to instantiate.

    Returns:
        Any: The populated proto message instance.
    """
    return ParseDict(data, message_cls(), ignore_unknown_fields=True)


def message_to_str(message_or_iterator: Any) -> str:
    """
    Convert a proto message or iterator to a string.

    Args:
        message_or_iterator: The message or async iterator to convert.

    Returns:
        str: A string representation of the message, or '<StreamingMessage>' for iterators.
    """
    if isinstance(message_or_iterator, AsyncIterator):
        return "<StreamingMessage>"
    return MessageToString(message_or_iterator, as_one_line=True, force_colon=True)


def message_to_pydantic(message: Any, pydantic_model: type[BaseModel]) -> BaseModel:
    """
    Map a proto message to a Pydantic model.

    Args:
        message: The proto message to map.
        pydantic_model: The Pydantic model class to instantiate.

    Returns:
        BaseModel: The populated Pydantic model instance.
    """
    return pydantic_model.model_validate(message, from_attributes=True)


def pydantic_to_message(model: BaseModel, message_cls: Any) -> Any:
    """
    Convert a Pydantic model to a proto message.

    Args:
        model: The Pydantic model to convert.
        message_cls: The proto message class to instantiate.

    Returns:
        Any: The populated proto message instance.
    """
    return Parse(model.model_dump_json(), message_cls(), ignore_unknown_fields=True)


def protoc_compile(
    proto: Path,
    python_out: str = ".",
    grpc_python_out: str = ".",
    proto_paths: Sequence[str] | None = None,
) -> None:
    """
    Compile a proto file into Python modules.

    Executes the protoc compiler to generate pb2 and pb2_grpc files.

    Args:
        proto: The Path to the proto file or directory.
        python_out: Directory for Python output files (default: ".").
        grpc_python_out: Directory for gRPC Python output files (default: ".").
        proto_paths: Optional list of include paths for protoc (default: None).

    Raises:
        FileNotFoundError: If the proto file or directory does not exist.
        RuntimeError: If the protoc compilation fails.
    """
    if not proto.exists():
        raise FileNotFoundError(f"Proto file or directory '{proto}' not found")
    if proto.is_file():
        proto_dir = proto.parent
    else:
        proto_dir = proto
    proto_files = [
        str(f) for f in proto_dir.iterdir() if f.is_file() and f.name.endswith(".proto")
    ]
    protoc_args = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--python_out={python_out}",
        f"--grpc_python_out={grpc_python_out}",
        "-I.",
    ]
    if proto_paths is not None:
        protoc_args.extend([f"-I{p}" for p in proto_paths])
    for file in proto_files:
        protoc_args.append(file)
    status_code = subprocess.call(protoc_args)
    if status_code != 0:
        logger.error(f"Command `{' '.join(protoc_args)}` [Err] {status_code=}")
        raise RuntimeError("Protobuf compilation failed")
    logger.info(f"Compiled {proto} success")