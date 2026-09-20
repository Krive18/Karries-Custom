from typing import Literal

from pydantic import BaseModel


class AdminProductStatusUpdate(BaseModel):
    status: Literal[1, 2]

