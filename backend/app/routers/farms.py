from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authentication.deps import can_edit_farm, get_current_user, get_farm_for_user
from ..database import get_db
from ..models import CropHistory, Farm, User
from ..schemas.farm import CropHistoryItem, FarmCreate, FarmOut, FarmUpdate
from ..utils.geo import point_geojson, polygon_area_ha

router = APIRouter(prefix="/api/farms", tags=["farms"])


def farm_out(farm: Farm, user: User) -> FarmOut:
    out = FarmOut.model_validate(farm)
    out.crop_history = [CropHistoryItem(crop_slug=h.crop_slug, season=h.season, year=h.year)
                        for h in sorted(farm.crop_history, key=lambda h: (h.year, h.season))]
    out.owner_name = farm.owner.name if farm.owner else None
    out.can_edit = can_edit_farm(user, farm)
    return out


def _apply(farm: Farm, body: FarmCreate, db: Session) -> None:
    data = body.model_dump(exclude={"crop_history", "growing_seasons"})
    for k, v in data.items():
        setattr(farm, k, v)
    farm.growing_seasons = [s.model_dump() for s in body.growing_seasons]
    farm.location = point_geojson(body.latitude, body.longitude)
    if body.boundary:
        farm.area_ha = round(polygon_area_ha(body.boundary), 3)
        farm.area_source = "computed_from_boundary"
    elif body.area_ha:
        farm.area_source = "user_entered"
    else:
        farm.area_source = None
    farm.crop_history.clear()
    db.flush()
    for item in body.crop_history:
        farm.crop_history.append(CropHistory(crop_slug=item.crop_slug, season=item.season, year=item.year))


@router.post("", response_model=FarmOut, status_code=201)
def create_farm(body: FarmCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = Farm(user_id=user.id)
    db.add(farm)
    _apply(farm, body, db)
    db.commit()
    db.refresh(farm)
    return farm_out(farm, user)


@router.get("", response_model=list[FarmOut])
def list_farms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Farm)
    if user.role == "organisation" and user.organisation_id:
        q = q.join(User, Farm.user_id == User.id).where(
            (User.organisation_id == user.organisation_id) | (Farm.user_id == user.id))
    elif user.role != "admin":
        q = q.where(Farm.user_id == user.id)
    farms = db.scalars(q.order_by(Farm.created_at.desc())).all()
    return [farm_out(f, user) for f in farms]


@router.get("/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return farm_out(get_farm_for_user(farm_id, db, user), user)


@router.put("/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: int, body: FarmUpdate, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user, write=True)
    moved = abs(farm.latitude - body.latitude) > 1e-6 or abs(farm.longitude - body.longitude) > 1e-6
    _apply(farm, body, db)
    if moved:
        # Observations belong to the old location; discard them so they are re-fetched.
        farm.observations.clear()
        farm.fetch_status.clear()
    db.commit()
    db.refresh(farm)
    return farm_out(farm, user)


@router.delete("/{farm_id}", status_code=204)
def delete_farm(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = get_farm_for_user(farm_id, db, user, write=True)
    db.delete(farm)
    db.commit()
