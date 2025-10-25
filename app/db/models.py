from sqlalchemy import Column, String, Integer, Boolean
from app.db.database import Base
# from sqlalchemy import uniqueconstraint 

class User(Base):
    __tablename__ = "users"  

    id = Column(Integer, primary_key= True, index = True)
    email= Column(String, unique= True, index= True, nullable= False)
    hashed_password= Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)

    # These columns will store the tokens from Google
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)

class Thermostat(Base):
    __tablename__ = "thermostat_status"

    id = Column(Integer, primary_key= True, index = True)
    device_name = Column(String, index= True, nullable= True)
    away = Column(Boolean, nullable=True)
    last_end_time = Column(String, nullable=True)
    preheat_time = Column(String, nullable=True)
    user_override = Column(String, nullable=True)