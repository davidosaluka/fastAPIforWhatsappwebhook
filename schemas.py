from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class userBase(BaseModel):
    username: str = Field(min_length=1, max_length=1000)
    display_phone_number: str = Field(min_length=1, max_length=1000)
    phone_number_id: str = Field(min_length=1, max_length=1000)
    
class userCreate(userBase):
    pass
 
class userResponse(userBase):

    model_config = ConfigDict(from_attributes=True)
    id: int

class apiRequestBase(BaseModel):
    object: str
    entry: list[Any]
    
    
class apiRequestCreate(apiRequestBase):
    pass
 
class apiPostRequestResponse(apiRequestBase):

    model_config = ConfigDict(from_attributes=True)
    id: int