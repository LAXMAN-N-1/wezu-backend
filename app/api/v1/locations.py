from __future__ import annotations
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api import deps
from app.models.location import Continent, Country, Region, City, Zone
from app.schemas import location as location_schema
from app.models.admin_user import AdminUser

router = APIRouter()

# --- CONTINENTS ---
@router.get("/continents", response_model=List[location_schema.ContinentRead])
def read_continents(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100) -> Any:
    return db.exec(select(Continent).offset(skip).limit(limit)).all()

@router.post("/continents", response_model=location_schema.ContinentRead)
def create_continent(*, db: Session = Depends(deps.get_db), continent_in: location_schema.ContinentCreate, current_user: AdminUser = Depends(deps.get_current_active_superuser)) -> Any:
    continent = Continent.from_orm(continent_in)
    db.add(continent)
    db.commit()
    db.refresh(continent)
    return continent

# --- COUNTRIES ---
@router.get("/countries", response_model=List[location_schema.CountryRead])
def read_countries(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100) -> Any:
    return db.exec(select(Country).offset(skip).limit(limit)).all()

@router.post("/countries", response_model=location_schema.CountryRead)
def create_country(*, db: Session = Depends(deps.get_db), country_in: location_schema.CountryCreate, current_user: AdminUser = Depends(deps.get_current_active_superuser)) -> Any:
    country = Country.from_orm(country_in)
    db.add(country)
    db.commit()
    db.refresh(country)
    return country

# --- REGIONS ---
@router.get("/regions", response_model=List[location_schema.RegionRead])
def read_regions(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100) -> Any:
    return db.exec(select(Region).offset(skip).limit(limit)).all()

@router.post("/regions", response_model=location_schema.RegionRead)
def create_region(*, db: Session = Depends(deps.get_db), region_in: location_schema.RegionCreate, current_user: AdminUser = Depends(deps.get_current_active_superuser)) -> Any:
    region = Region.from_orm(region_in)
    db.add(region)
    db.commit()
    db.refresh(region)
    return region

# --- CITIES ---
@router.get("/cities", response_model=List[location_schema.CityRead])
def read_cities(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100) -> Any:
    return db.exec(select(City).offset(skip).limit(limit)).all()

@router.post("/cities", response_model=location_schema.CityRead)
def create_city(*, db: Session = Depends(deps.get_db), city_in: location_schema.CityCreate, current_user: AdminUser = Depends(deps.get_current_active_superuser)) -> Any:
    city = City.from_orm(city_in)
    db.add(city)
    db.commit()
    db.refresh(city)
    return city

# --- ZONES ---
@router.get("/zones", response_model=List[location_schema.ZoneRead])
def read_zones(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100) -> Any:
    return db.exec(select(Zone).offset(skip).limit(limit)).all()

@router.post("/zones", response_model=location_schema.ZoneRead)
def create_zone(*, db: Session = Depends(deps.get_db), zone_in: location_schema.ZoneCreate, current_user: AdminUser = Depends(deps.get_current_active_superuser)) -> Any:
    zone = Zone.from_orm(zone_in)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone
