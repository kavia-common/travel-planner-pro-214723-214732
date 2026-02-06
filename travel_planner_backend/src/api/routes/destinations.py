from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from src.db.models import Destination
from src.db.session import get_db
from src.schemas.travel import DestinationSearchResponse, DestinationSearchResult

router = APIRouter(prefix="/api/destinations", tags=["Destinations"])


@router.get(
    "/search",
    response_model=DestinationSearchResponse,
    summary="Search destinations",
    description=(
        "Case-insensitive partial text search over destinations. "
        "Matches on `name` and optionally `country`/`city`. "
        "Returns a paginated list."
    ),
    operation_id="search_destinations",
)
def search_destinations(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query text (partial match; case-insensitive)",
    ),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    include_country: bool = Query(True, description="Include `country` field in search matching"),
    include_city: bool = Query(True, description="Include `city` field in search matching"),
) -> DestinationSearchResponse:
    """Search destinations by partial match.

    Args:
        q: Query string to search for (case-insensitive, partial match).
        db: SQLAlchemy Session (FastAPI dependency).
        limit: Page size.
        offset: Pagination offset.
        include_country: Whether to include country in matching.
        include_city: Whether to include city in matching.

    Returns:
        DestinationSearchResponse: Paginated matching destinations.

    Raises:
        HTTPException: 422 if q is blank/whitespace.
    """
    q_stripped = q.strip()
    if q_stripped == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q must not be blank",
        )

    pattern = f"%{q_stripped}%"

    conditions = [Destination.name.ilike(pattern)]
    if include_country:
        conditions.append(Destination.country.ilike(pattern))
    if include_city:
        conditions.append(Destination.city.ilike(pattern))

    where_clause = or_(*conditions)

    total_stmt = select(func.count()).select_from(Destination).where(where_clause)
    total = db.execute(total_stmt).scalar_one()

    # Prefer popularity when present; fall back to name for stable ordering.
    # Note: score is not computed here; schema keeps it optional for future improvements.
    stmt = (
        select(Destination)
        .where(where_clause)
        .order_by(desc(Destination.popularity).nulls_last(), Destination.name.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).scalars().all()

    items = [
        DestinationSearchResult(
            id=row.id,
            name=row.name,
            country=row.country,
            city=row.city,
            popularity=row.popularity,
            score=None,
        )
        for row in rows
    ]

    return DestinationSearchResponse(total=total, limit=limit, offset=offset, items=items)
