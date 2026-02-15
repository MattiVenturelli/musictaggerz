from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Setting
from app.schemas import SettingResponse, SettingsUpdateRequest

router = APIRouter()


@router.get("", response_model=List[SettingResponse])
def get_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()


@router.put("")
def update_settings(request: SettingsUpdateRequest, db: Session = Depends(get_db)):
    updated = []
    for key, value in request.settings.items():
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = str(value)
            updated.append(key)
        else:
            new_setting = Setting(key=key, value=str(value), value_type="string")
            db.add(new_setting)
            updated.append(key)
    db.commit()
    return {"updated": updated}
