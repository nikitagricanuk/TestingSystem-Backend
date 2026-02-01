from fastapi import FastAPI
from .routers import results
from .services.testing_engine.routers import sessions
from .services.auth.routers import auth


def create_app() -> FastAPI:
    app = FastAPI(title='Student Testing System API', version='1.0.0')
    # Example global dependency:
    # app.dependency_overrides[get_token_header] = lambda: None
    app.include_router(results.router, prefix="", tags=['results'])
    app.include_router(sessions.router, prefix="", tags=['sessions'])
    app.include_router(auth.router, prefix="/v1/auth", tags=['auth'])
    return app


app = create_app()
