from pydantic import BaseModel
from fast_grpc import FastGRPC, BaseMiddleware

app = FastGRPC(
    service_name="TestService",
    proto="test.proto",
    auto_gen_proto=True,
)


class CustomMiddleware(BaseMiddleware):
    async def __call__(self, method, request, context, *args, **kwargs):
        print("Custom worked")
        return await method(request, context, *args, **kwargs)


class HelloWorldRequest(BaseModel):
    name: str


class HelloWorldReply(BaseModel):
    message: str


@app.unary_unary()
async def say_hello(request: HelloWorldRequest) -> HelloWorldReply:
    return HelloWorldReply(message=f"Hello world, {request.name}")


if __name__ == "__main__":
    app.add_middleware(middlewares=[CustomMiddleware()])
    app.run()
