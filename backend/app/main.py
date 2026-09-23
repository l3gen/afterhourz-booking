import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, appointments, auth_routes, public, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()  # fails fast on insecure/missing config
is_prod = settings.env == "prod"

app = FastAPI(
    title="AfterHourzKutz Booking API",
    docs_url=None if is_prod else "/api/docs",
    redoc_url=None,
    openapi_url=None if is_prod else "/api/openapi.json",
)

# In AWS the site and API share one CloudFront origin, so CORS only matters for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["authorization", "content-type"],
)

for r in (public.router, auth_routes.router, appointments.router, admin.router, webhooks.router):
    app.include_router(r)
