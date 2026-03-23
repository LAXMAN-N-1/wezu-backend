from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Continent(SQLModel, table=True):
    __tablename__ = "continents"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    
    countries: List["Country"] = Relationship(back_populates="continent")

class Country(SQLModel, table=True):
    __tablename__ = "countries"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    continent_id: int = Field(foreign_key="continents.id")
    
    continent: Continent = Relationship(back_populates="countries")
    regions: List["Region"] = Relationship(back_populates="country")

class Region(SQLModel, table=True):
    __tablename__ = "regions"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    country_id: int = Field(foreign_key="countries.id")
    
    country: Country = Relationship(back_populates="regions")
    cities: List["City"] = Relationship(back_populates="region")

class City(SQLModel, table=True):
    __tablename__ = "cities"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    region_id: int = Field(foreign_key="regions.id")
    
    region: Region = Relationship(back_populates="cities")
    zones: List["Zone"] = Relationship(back_populates="city")

class Zone(SQLModel, table=True):
    __tablename__ = "zones"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    city_id: int = Field(foreign_key="cities.id")
    
    city: City = Relationship(back_populates="zones")
    stations: List["Station"] = Relationship(back_populates="zone")
