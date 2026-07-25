from fastapi import APIRouter

from store.daily_repo import get_stats
from store.realtime_repo import get_latest_snapshot

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def stats():
    db_stats = get_stats()
    latest_rt = get_latest_snapshot()
    return {
        **db_stats,
        "realtime_snapshot_count": len(latest_rt),
    }
