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