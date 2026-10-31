"""Legacy learner authentication is disabled; existing data is retained."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
@router.post("/login")
@router.post("/logout")
@router.get("/me")
def disabled_auth() -> None:
    raise HTTPException(status_code=410, detail="Học trực tiếp, không cần đăng nhập.")
