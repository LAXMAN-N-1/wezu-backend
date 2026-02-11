from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# Base Schemas
class ContinentBase(BaseModel):
    name: str

class CountryBase(BaseModel):
    name: str
    continent_id: int

class RegionBase(BaseModel):
    name: str
    country_id: int

class CityBase(BaseModel):
    name: str
    region_id: int

class ZoneBase(BaseModel):
    name: str
    city_id: int

# Create Schemas
class ContinentCreate(ContinentBase): pass
class CountryCreate(CountryBase): pass
class RegionCreate(RegionBase): pass
class CityCreate(CityBase): pass
class ZoneCreate(ZoneBase): pass

# Read Schemas
class ContinentRead(ContinentBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CountryRead(CountryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RegionRead(RegionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CityRead(CityBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ZoneRead(ZoneBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
