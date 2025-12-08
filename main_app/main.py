from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import users, vehicles, bookings, owner
from .routers import owner_additional, messaging, websocket, error_audit
from .payment import router as payment_router
from .logging_config import setup_logging
from .middleware import LoggingMiddleware
from .error_middleware import ErrorAuditMiddleware

# Initialize logging
setup_logging()

app = FastAPI(
    title="Redi Rental API",
    description="Vehicle rental platform API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)
# Add error audit middleware
app.add_middleware(ErrorAuditMiddleware)

# Include routers
app.include_router(users.router)
app.include_router(vehicles.router)
app.include_router(bookings.router)
app.include_router(owner.router)
app.include_router(owner_additional.router)
app.include_router(messaging.router)
app.include_router(websocket.router)
app.include_router(payment_router.router)
app.include_router(error_audit.router)

@app.get("/")
def root():
    return {"message": "Redi Rental API", "version": "1.0.1"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

