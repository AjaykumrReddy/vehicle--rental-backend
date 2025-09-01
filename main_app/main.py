from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import users, vehicles, bookings, owner
from .routers import owner_additional

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

# Include routers
app.include_router(users.router)
app.include_router(vehicles.router)
app.include_router(bookings.router)
app.include_router(owner.router)
app.include_router(owner_additional.router)

@app.get("/")
def root():
    return {"message": "Redi Rental API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

