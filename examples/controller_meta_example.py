from typing import AsyncIterator

from fast_grpc import FastGRPC, ControllerMeta
from pydantic import BaseModel


class TestRequest(BaseModel):
    name: str


class TestResponse(BaseModel):
    message: str


class ServiceTest(
    metaclass=ControllerMeta,
    proto_path="protos/",
    middlewares=[],
    exceptions={},
):
    @staticmethod
    async def unary_unary(request: TestRequest) -> TestResponse:
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
    app.add_service(ServiceTest())
    app.run()
