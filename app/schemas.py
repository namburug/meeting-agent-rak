from pydantic import BaseModel


class ItemUpdate(BaseModel):
    text: str | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    due_date_resolved: str | None = None
    priority: str | None = None


class ApproveRejectBody(BaseModel):
    actor: str = "human:demo-user"


class FinalizeBody(BaseModel):
    actor: str = "human:demo-user"
