from __future__ import annotations
from datetime import UTC, datetime
import random
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import string


def generate_order_number():
    def segment(length):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))
    
    return f"{segment(7)}-{segment(7)}"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_phone_number:  Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    wa_id : Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name : Mapped[str] = mapped_column(String, unique=False, nullable=False)
    
    #api_requests: Mapped[list[apiRequest]] = relationship(back_populates="author") 


class apiRequest(Base):
    __tablename__ = "apiRequests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    date_posted: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    #author: Mapped[User] = relationship(back_populates="api_requests")



class Orders(Base):
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(16), default=generate_order_number, unique=True, nullable=False)

    