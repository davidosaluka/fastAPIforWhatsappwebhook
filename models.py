from __future__ import annotations
from datetime import UTC, datetime, timedelta
import random
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
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
    sender_wa_number:      Mapped[str] = mapped_column(String(50), nullable=False) 
    rider_wa_number:      Mapped[str] = mapped_column(String(50), nullable=True) 
    recipient_phone_number:      Mapped[str] = mapped_column(String(50), nullable=False)  
    package_description: Mapped[str] = mapped_column(String(50), nullable=True)  
    customer_initial_offered_price: Mapped[str] = mapped_column("customer_intital_offered_price", String, nullable=True)
    final_price_agreed_by_cust_and_rider: Mapped[str] = mapped_column(String, nullable=True)
    status:       Mapped[str] = mapped_column(String(50), nullable=False)             # "awaiting_pickup", "awaiting_dropoff", "confirmed" etc.
    pickup_location_name: Mapped[str] = mapped_column(String, nullable=True)
    pickup_lat:   Mapped[float] = mapped_column(Float, nullable=True)
    pickup_lng :   Mapped[float] = mapped_column(Float, nullable=True)
    dropoff_lat :   Mapped[float] = mapped_column(Float, nullable=True)
    dropoff_lng  :   Mapped[float] = mapped_column(Float, nullable=True)
    dropoff_location_name: Mapped[str] = mapped_column(String, nullable=True)
    package_image_id: Mapped[str] = mapped_column(String, nullable=True)
    delivery_progression_status: Mapped[str] = mapped_column(String, nullable=True)
    sla_expires_by: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC) + timedelta(minutes=30))
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    @property
    def customer_intital_offered_price(self):
        return self.customer_initial_offered_price

    @customer_intital_offered_price.setter
    def customer_intital_offered_price(self, value):
        self.customer_initial_offered_price = value


class Riders(Base):
    __tablename__ = "riders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    rider_wa_number: Mapped[str] = mapped_column(String(50), nullable=False)
    rider_phonenumber_2: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    kyc_status: Mapped[str] = mapped_column(String(50), nullable=False)
    availability_status: Mapped[str] = mapped_column("availabilty_status", String(50), nullable=False)

    @property
    def availabilty_status(self):
        return self.availability_status

    @availabilty_status.setter
    def availabilty_status(self, value):
        self.availability_status = value


    