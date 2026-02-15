import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Setting
from app.schemas import SettingResponse, SettingsUpdateRequest
from app.config import settings as app_settings

router = APIRouter()


@router.get("", response_model=List[SettingResponse])
def get_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()


@router.put("")
def update_settings(request: SettingsUpdateRequest, db: Session = Depends(get_db)):
    updated = []
    for key, value in request.settings.items():
        if isinstance(value, list):
            str_value = json.dumps(value)
        else:
            str_value = str(value)

        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = str_value
            updated.append(key)
        else:
            new_setting = Setting(key=key, value=str_value, value_type="string")
            db.add(new_setting)
            updated.append(key)
    db.commit()

    # Sync to runtime config so core modules pick up the new values
    for key, value in request.settings.items():
        str_value = json.dumps(value) if isinstance(value, list) else str(value)
        app_settings.apply_from_db(key, str_value)

    return {"updated": updated}
