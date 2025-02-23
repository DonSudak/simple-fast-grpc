import uvicorn

from fast_grpc import ApiGenerator

api = ApiGenerator(proto_path="proto/")
app = api.generate_api()
uvicorn.run(app)
