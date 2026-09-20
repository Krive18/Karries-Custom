from app.main import create_app


# Production server entrypoint: expose customer, manager, and developer APIs
# through one internal Uvicorn process behind Nginx.
app = create_app("all")
