from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes  = True,
        use_enum_values  = True,
        populate_by_name = True,
    )


class BaseResponseSchema(BaseSchema):
    id         : UUID
    created_at : datetime
    updated_at : datetime
    created_by : Optional[UUID] = None
    updated_by : Optional[UUID] = None


class PaginatedResponse(BaseSchema):
    total : int
    page  : int
    size  : int
    pages : int
    items : list


class MessageResponse(BaseSchema):
    message : str
    success : bool = True
