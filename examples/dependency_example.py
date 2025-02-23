from typing import AsyncIterator

from fast_grpc import FastGRPC, ControllerMeta, Depends
from pydantic import BaseModel


class TestRequest(BaseModel):
    name: str


class TestResponse(BaseModel):
    message: str


class ContextManagerAsync:
    def __init__(self): ...

    async def __aenter__(self):
        print("enter")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("exit")


class ContextManager:
    def __init__(self): ...

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("exit")


async def async_gen():
    print("async before yield")
    yield 1
    print("async after yield")


def sync_gen():
    print("before yield")
    yield 1
    print("after yield")


class LayersDependency:
    def __init__(self, some_depends=Depends(sync_gen)): ...

    # print("some depends")
    # print(some_depends)


async def async_context_manager():
    async with ContextManagerAsync() as _:
        print("async context manager")
        return True


def context_manager():
    with ContextManager() as _:
        print("context manager")
        return True


def sync_dependency():
    return "sync dependency"


async def async_dependency():
    return "async dependency"


async def inner_layer_dependency():
    return "123"


async def layer_dependencies(inner=Depends(inner_layer_dependency)):
    return inner


class ControllerTest(
    metaclass=ControllerMeta,
    proto_path="proto/",
):
    @staticmethod
    async def say_hello(
        request: TestRequest,
        async_ctx=Depends(async_context_manager),
        sync_ctx=Depends(sync_dependency),
        async_dependency=Depends(async_dependency),
        sync_dependency=Depends(sync_dependency),
        async_gen=Depends(async_gen),
        sync_gen=Depends(sync_gen),
        layers_dependencies_class=Depends(LayersDependency),
        layer_dependencies=Depends(layer_dependencies),
    ) -> TestResponse:
        print(async_ctx)
        print(sync_ctx)
        print(async_dependency)
        print(sync_dependency)
        print(async_gen)
        print(sync_gen)
        print(layers_dependencies_class)
        print(layer_dependencies)
        return TestResponse(message=request.name)

    @staticmethod
    async def stream_unary(request: AsyncIterator[TestRequest]) -> TestResponse:
        response = TestResponse(message="SayHello:")
        async for message in request:
            response.message += f" {message.name}"
        return response

    @staticmethod
    async def unary_stream(request: TestRequest) -> AsyncIterator[TestResponse]:
        for i in range(3):
            yield TestResponse(message=f"SayHello: {request.name} {i}")

    @staticmethod
    async def stream_stream(
        request: AsyncIterator[TestRequest],
    ) -> AsyncIterator[TestResponse]:
        async for message in request:
            yield TestResponse(message=f"SayHello: {message.name}")


if __name__ == "__main__":
    app = FastGRPC()
    app.add_service(ControllerTest())
    app.run()
