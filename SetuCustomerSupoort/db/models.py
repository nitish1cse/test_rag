from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Secret(Base):
    __tablename__ = "secrets"
    key = Column(String, primary_key=True)
    value = Column(String)
