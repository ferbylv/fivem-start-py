# models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, BigInteger, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    nickname = Column(String(50))
    license = Column(String(255), index=True, nullable=True)
    cash = Column(BigInteger, default=0)
    bank = Column(BigInteger, default=0)
    is_bound = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联关系
    vehicles = relationship("UserVehicle", back_populates="owner")
    inventory = relationship("UserInventory", back_populates="owner")

class UserVehicle(Base):
    __tablename__ = "user_vehicles"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    plate = Column(String(10), unique=True, nullable=False)
    model_name = Column(String(50), nullable=False)
    type = Column(String(20), default="轿车")
    image_url = Column(String(255))
    state = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="vehicles")

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    type = Column(String(20), default="消耗品")
    image_url = Column(String(255))
    description = Column(String(255))

    # 反向关联（可选）
    inventory_records = relationship("UserInventory", back_populates="item_info")

class UserInventory(Base):
    __tablename__ = "user_inventory"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    count = Column(Integer, default=1)

    owner = relationship("User", back_populates="inventory")
    item_info = relationship("Item", back_populates="inventory_records")

class Banner(Base):
    __tablename__ = "banners"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    desc = Column(String(255))
    image_url = Column(String(255), nullable=False)
    link_url = Column(String(255))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())