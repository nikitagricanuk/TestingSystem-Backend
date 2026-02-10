from fastapi import FastAPI
from .routers import results, health
from .services.testing_engine.routers import sessions
from .services.auth.routers import auth


def create_app() -> FastAPI:
    app = FastAPI(title='Student Testing System API', version='1.0.0')
    # Example global dependency:
    # app.dependency_overrides[get_token_header] = lambda: None
    app.include_router(health.router, prefix="", tags=['health'])
    app.include_router(results.router, prefix="", tags=['results'], include_in_schema=False)
    app.include_router(results.router, prefix="/v1", tags=['results'])
    app.include_router(sessions.router, prefix="", tags=['sessions'], include_in_schema=False)
    app.include_router(sessions.router, prefix="/v1", tags=['sessions'])
    app.include_router(auth.router, prefix="/v1/auth", tags=['auth'])
    return app


app = create_app()
