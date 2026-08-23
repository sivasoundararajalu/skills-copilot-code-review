"""
Announcement endpoints for the High School Management System API
"""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementInput(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    expiration_date: date
    start_date: Optional[date] = None


def _require_teacher(teacher_username: Optional[str]) -> Dict[str, Any]:
    """Verify teacher_username belongs to an existing teacher, raising 401 otherwise."""
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    return teacher


def _validate_dates(data: AnnouncementInput) -> None:
    if data.start_date and data.start_date > data.expiration_date:
        raise HTTPException(
            status_code=400, detail="Start date must be before the expiration date")


def _serialize(announcement: Dict[str, Any]) -> Dict[str, Any]:
    announcement = dict(announcement)
    announcement["id"] = announcement.pop("_id")
    return announcement


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all announcements that are currently active (public endpoint used for the banner)"""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [{"start_date": None}, {"start_date": {"$lte": today}}]
    }

    return [_serialize(a) for a in announcements_collection.find(query)]


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements - requires teacher authentication"""
    _require_teacher(teacher_username)

    announcements = announcements_collection.find().sort("expiration_date", 1)
    return [_serialize(a) for a in announcements]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(data: AnnouncementInput, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Create a new announcement - requires teacher authentication"""
    teacher = _require_teacher(teacher_username)
    _validate_dates(data)

    announcement = {
        "_id": str(uuid.uuid4()),
        "message": data.message,
        "start_date": data.start_date.isoformat() if data.start_date else None,
        "expiration_date": data.expiration_date.isoformat(),
        "created_by": teacher["username"]
    }
    announcements_collection.insert_one(announcement)

    return _serialize(announcement)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(announcement_id: str, data: AnnouncementInput, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Update an existing announcement - requires teacher authentication"""
    _require_teacher(teacher_username)
    _validate_dates(data)

    existing = announcements_collection.find_one({"_id": announcement_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updates = {
        "message": data.message,
        "start_date": data.start_date.isoformat() if data.start_date else None,
        "expiration_date": data.expiration_date.isoformat(),
    }
    announcements_collection.update_one(
        {"_id": announcement_id}, {"$set": updates})

    return _serialize({**existing, **updates})


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, str]:
    """Delete an announcement - requires teacher authentication"""
    _require_teacher(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
