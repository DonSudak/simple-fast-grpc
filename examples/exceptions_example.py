from pydantic import BaseModel
from fast_grpc import FastGRPC, ControllerContext, BaseMiddleware, GRPCException
import grpc

app = FastGRPC(
    service_name="TestService",
    proto="test.proto",
    auto_gen_proto=True,
)


class TestExc(Exception): ...


async def exc_handler(request, context: ControllerContext, exc: TestExc):
    await context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details="Some exception")


class Test(BaseModel):
    a: str


class HelloWorldRequest(BaseModel):
    name: str


class HelloWorldReply(BaseModel):
    message: str


@app.unary_unary()
async def say_hello(request: HelloWorldRequest) -> HelloWorldReply:
    # a = Test(a=1)
    # raise TestExc("Test exception")
    # raise GRPCException(status=grpc.StatusCode.UNKNOWN, details="Test grpc exception")
    return HelloWorldReply(message=f"Hello world, {request.name}")


if __name__ == "__main__":
    app.add_exception_handler(exceptions={TestExc: exc_handler})
    app.run()
