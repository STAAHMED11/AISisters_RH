from sqlalchemy.orm import Session

from .models import AuditLog


def log_event(db: Session, actor: str, action: str, entity: str = "", entity_id: int | None = None, **payload):
    db.add(AuditLog(actor=actor, action=action, entity=entity, entity_id=entity_id, payload=payload))
    db.commit()
