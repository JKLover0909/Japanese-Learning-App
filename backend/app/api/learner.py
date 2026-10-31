"""Bootstrap the browser cookie before parallel learner API requests."""

from fastapi import APIRouter

from app.api.deps import AnonymousLearner

router = APIRouter(prefix="/learner", tags=["learner"])


@router.post("/init")
def initialize(user: AnonymousLearner) -> dict[str, str]:
    return {"status": "ok"}
