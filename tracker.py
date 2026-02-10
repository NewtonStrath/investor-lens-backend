# backend/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import cv2
import threading
import asyncio

# -------------------------------
# Pydantic Models
# -------------------------------

class Location(BaseModel):
    lat: float
    lng: float

class User(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str
    lastLogin: str
    avatar: str

class Violation(BaseModel):
    id: str
    type: str
    time: str
    location: str
    value: str
    limit: str

class Vehicle(BaseModel):
    id: str
    registrationNumber: str
    model: str
    capacity: str
    status: str
    currentDriverId: Optional[str] = None
    lastServiceDate: str
    nextServiceDate: str
    insuranceExpiry: str
    fuelEfficiency: float
    totalDistance: float
    location: Location
    locationName: Optional[str] = None
    speed: Optional[float] = 0.0
    violations: List[Violation] = []
    fuelLevel: Optional[float] = 0.0  # in liters

class Driver(BaseModel):
    id: str
    name: str
    licenseNumber: str
    licenseExpiry: str
    phone: str
    status: str
    assignedVehicleId: Optional[str] = None
    totalTrips: int
    totalDistance: float
    rating: float
    avatar: str
    joinedDate: str

class Trip(BaseModel):
    id: str
    origin: str
    destination: str
    cargoType: str
    distance: float
    expectedDuration: str
    vehicleId: str
    driverId: str
    status: str
    startDate: str
    endDate: Optional[str] = None
    cost: float

class FuelRecord(BaseModel):
    id: str
    date: str
    vehicleId: str
    driverId: str
    quantity: float
    cost: float
    location: str
    tripId: str
    efficiency: float
    isAnomaly: bool

class MaintenanceRecord(BaseModel):
    id: str
    vehicleId: str
    date: str
    type: str
    description: str
    cost: float
    provider: str
    status: str

class Notification(BaseModel):
    id: str
    type: str
    title: str
    message: str
    timestamp: str
    read: bool
    category: str

class KPI(BaseModel):
    label: str
    value: str | float
    change: float
    trend: str
    period: str

class VehicleLocationUpdate(BaseModel):
    lat: float
    lng: float
    speed: Optional[float] = None
    fuelLevel: Optional[float] = None

# -------------------------------
# Mock Data
# -------------------------------

users = [
    {"id":"u1","name":"Alex Mwangi","email":"alex@fleetpulse.com","role":"Admin","status":"Active","lastLogin":"2023-10-25T08:30:00Z","avatar":"https://i.pravatar.cc/150?u=u1"},
    {"id":"u2","name":"Sarah Okafor","email":"sarah@fleetpulse.com","role":"Dispatcher","status":"Active","lastLogin":"2023-10-25T09:15:00Z","avatar":"https://i.pravatar.cc/150?u=u2"},
]

vehicles = [
    {
        "id": "v1",
        "registrationNumber": "KBA 123A",
        "model": "Mercedes Actros",
        "capacity": "20T",
        "status": "On Trip",
        "currentDriverId": "d1",
        "lastServiceDate": "2023-09-15",
        "nextServiceDate": "2023-12-15",
        "insuranceExpiry": "2024-01-20",
        "fuelEfficiency": 3.2,
        "totalDistance": 125000,
        "location": {"lat": -1.2921, "lng": 36.8219},
        "locationName": "Nairobi CBD",
        "speed": 75,
        "violations": [
            {"id": "vi1", "type": "Overspeed", "time": "09:45 AM", "location": "Nairobi CBD", "value": "120 km/h", "limit": "100 km/h"},
            {"id": "vi2", "type": "Harsh Braking", "time": "11:20 AM", "location": "Thika Road", "value": "Sharp Stop", "limit": "Safe Stop"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v2",
        "registrationNumber": "KBC 456B",
        "model": "Scania R450",
        "capacity": "25T",
        "status": "Available",
        "currentDriverId": "d2",
        "lastServiceDate": "2023-10-01",
        "nextServiceDate": "2024-01-01",
        "insuranceExpiry": "2024-02-15",
        "fuelEfficiency": 3.5,
        "totalDistance": 98000,
        "location": {"lat": -4.0435, "lng": 39.6682},
        "locationName": "Mombasa",
        "speed": 0,
        "violations": [
            {"id": "vi3", "type": "Idling", "time": "08:10 AM", "location": "Depot", "value": "15 min", "limit": "5 min"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v3",
        "registrationNumber": "KBD 789C",
        "model": "Volvo FH16",
        "capacity": "30T",
        "status": "Maintenance",
        "currentDriverId": "d3",
        "lastServiceDate": "2023-08-20",
        "nextServiceDate": "2023-11-20",
        "insuranceExpiry": "2023-11-10",
        "fuelEfficiency": 2.8,
        "totalDistance": 156000,
        "location": {"lat": -0.0917, "lng": 34.768},
        "locationName": "Nakuru",
        "speed": 0,
        "violations": [
            {"id": "vi4", "type": "Route Deviation", "time": "10:10 AM", "location": "Industrial Area", "value": "3 km", "limit": "0.5 km"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v4",
        "registrationNumber": "KBE 234D",
        "model": "MAN TGX",
        "capacity": "22T",
        "status": "On Trip",
        "currentDriverId": "d4",
        "lastServiceDate": "2023-09-10",
        "nextServiceDate": "2023-12-10",
        "insuranceExpiry": "2024-01-15",
        "fuelEfficiency": 3.1,
        "totalDistance": 110000,
        "location": {"lat": -1.3733, "lng": 36.8580},
        "locationName": "Ngong",
        "speed": 65,
        "violations": [
            {"id": "vi5", "type": "Overspeed", "time": "08:30 AM", "location": "Ngong Rd", "value": "105 km/h", "limit": "90 km/h"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v5",
        "registrationNumber": "KBF 567E",
        "model": "DAF XF",
        "capacity": "28T",
        "status": "Available",
        "currentDriverId": "d5",
        "lastServiceDate": "2023-07-25",
        "nextServiceDate": "2023-11-25",
        "insuranceExpiry": "2023-12-20",
        "fuelEfficiency": 3.4,
        "totalDistance": 132000,
        "location": {"lat": -3.3869, "lng": 36.6820},
        "locationName": "Naivasha",
        "speed": 0,
        "violations": [],
        "fuelLevel": 200.0
    },
    {
        "id": "v6",
        "registrationNumber": "KBG 890F",
        "model": "Iveco Stralis",
        "capacity": "24T",
        "status": "On Trip",
        "currentDriverId": "d6",
        "lastServiceDate": "2023-08-18",
        "nextServiceDate": "2023-12-18",
        "insuranceExpiry": "2024-01-25",
        "fuelEfficiency": 3.0,
        "totalDistance": 140000,
        "location": {"lat": -1.2864, "lng": 36.8172},
        "locationName": "Embakasi",
        "speed": 70,
        "violations": [
            {"id": "vi6", "type": "Harsh Acceleration", "time": "07:55 AM", "location": "Mombasa Rd", "value": "Rapid Start", "limit": "Safe Start"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v7",
        "registrationNumber": "KBH 112G",
        "model": "Volvo FMX",
        "capacity": "26T",
        "status": "Maintenance",
        "currentDriverId": "d7",
        "lastServiceDate": "2023-06-20",
        "nextServiceDate": "2023-10-20",
        "insuranceExpiry": "2023-11-05",
        "fuelEfficiency": 2.9,
        "totalDistance": 150000,
        "location": {"lat": -2.1521, "lng": 37.3089},
        "locationName": "Kitui",
        "speed": 0,
        "violations": [],
        "fuelLevel": 200.0
    },
    {
        "id": "v8",
        "registrationNumber": "KBI 334H",
        "model": "Mercedes Atego",
        "capacity": "18T",
        "status": "Available",
        "currentDriverId": "d8",
        "lastServiceDate": "2023-07-10",
        "nextServiceDate": "2023-11-10",
        "insuranceExpiry": "2023-12-30",
        "fuelEfficiency": 3.3,
        "totalDistance": 90000,
        "location": {"lat": -3.0456, "lng": 39.6592},
        "locationName": "Malindi",
        "speed": 0,
        "violations": [
            {"id": "vi7", "type": "Overspeed", "time": "09:00 AM", "location": "Kisumu Rd", "value": "100 km/h", "limit": "80 km/h"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v9",
        "registrationNumber": "KBJ 556I",
        "model": "Scania P410",
        "capacity": "27T",
        "status": "On Trip",
        "currentDriverId": "d9",
        "lastServiceDate": "2023-09-05",
        "nextServiceDate": "2023-12-05",
        "insuranceExpiry": "2024-01-10",
        "fuelEfficiency": 3.2,
        "totalDistance": 123000,
        "location": {"lat": -1.2921, "lng": 36.9000},
        "locationName": "Karen",
        "speed": 60,
        "violations": [
            {"id": "vi8", "type": "Harsh Braking", "time": "10:15 AM", "location": "Langata Rd", "value": "Sharp Stop", "limit": "Safe Stop"}
        ],
        "fuelLevel": 200.0
    },
    {
        "id": "v10",
        "registrationNumber": "KBK 778J",
        "model": "MAN TGS",
        "capacity": "30T",
        "status": "Available",
        "currentDriverId": "d10",
        "lastServiceDate": "2023-08-12",
        "nextServiceDate": "2023-11-12",
        "insuranceExpiry": "2024-02-01",
        "fuelEfficiency": 3.6,
        "totalDistance": 95000,
        "location": {"lat": -0.4200, "lng": 36.9500},
        "locationName": "Naivasha",
        "speed": 0,
        "violations": [],
        "fuelLevel": 200.0,
    }
]

drivers = [
    {"id":"d1","name":"John Kamau","licenseNumber":"DL123456","licenseExpiry":"2025-05-20","phone":"+254 712 345 678","status":"On Trip","assignedVehicleId":"v1","totalTrips":145,"totalDistance":45000,"rating":4.8,"avatar":"https://i.pravatar.cc/150?u=d1","joinedDate":"2021-03-15"},
    {"id":"d2","name":"Mary Wanjiku","licenseNumber":"DL234567","licenseExpiry":"2026-01-15","phone":"+254 723 456 789","status":"Available","assignedVehicleId":"v2","totalTrips":120,"totalDistance":38000,"rating":4.6,"avatar":"https://i.pravatar.cc/150?u=d2","joinedDate":"2021-07-22"},
    {"id":"d3","name":"Peter Otieno","licenseNumber":"DL345678","licenseExpiry":"2025-11-10","phone":"+254 734 567 890","status":"Maintenance","assignedVehicleId":"v3","totalTrips":160,"totalDistance":50000,"rating":4.7,"avatar":"https://i.pravatar.cc/150?u=d3","joinedDate":"2020-12-05"},
    {"id":"d4","name":"Lucy Achieng","licenseNumber":"DL456789","licenseExpiry":"2026-03-12","phone":"+254 745 678 901","status":"On Trip","assignedVehicleId":"v4","totalTrips":90,"totalDistance":25000,"rating":4.5,"avatar":"https://i.pravatar.cc/150?u=d4","joinedDate":"2022-01-20"},
    {"id":"d5","name":"Michael Njoroge","licenseNumber":"DL567890","licenseExpiry":"2025-09-18","phone":"+254 756 789 012","status":"Available","assignedVehicleId":"v5","totalTrips":110,"totalDistance":30000,"rating":4.6,"avatar":"https://i.pravatar.cc/150?u=d5","joinedDate":"2021-05-11"},
    {"id":"d6","name":"Grace Mwende","licenseNumber":"DL678901","licenseExpiry":"2026-05-25","phone":"+254 767 890 123","status":"On Trip","assignedVehicleId":"v6","totalTrips":140,"totalDistance":42000,"rating":4.7,"avatar":"https://i.pravatar.cc/150?u=d6","joinedDate":"2020-10-30"},
    {"id":"d7","name":"David Kiptoo","licenseNumber":"DL789012","licenseExpiry":"2025-12-05","phone":"+254 778 901 234","status":"Maintenance","assignedVehicleId":"v7","totalTrips":130,"totalDistance":39000,"rating":4.6,"avatar":"https://i.pravatar.cc/150?u=d7","joinedDate":"2021-03-18"},
    {"id":"d8","name":"Faith Nyambura","licenseNumber":"DL890123","licenseExpiry":"2026-02-14","phone":"+254 789 012 345","status":"Available","assignedVehicleId":"v8","totalTrips":100,"totalDistance":27000,"rating":4.5,"avatar":"https://i.pravatar.cc/150?u=d8","joinedDate":"2022-02-12"},
    {"id":"d9","name":"Samuel Kariuki","licenseNumber":"DL901234","licenseExpiry":"2025-08-30","phone":"+254 790 123 456","status":"On Trip","assignedVehicleId":"v9","totalTrips":150,"totalDistance":46000,"rating":4.8,"avatar":"https://i.pravatar.cc/150?u=d9","joinedDate":"2021-06-25"},
    {"id":"d10","name":"Angela Chebet","licenseNumber":"DL012345","licenseExpiry":"2026-04-20","phone":"+254 701 234 567","status":"Available","assignedVehicleId":"v10","totalTrips":95,"totalDistance":24000,"rating":4.6,"avatar":"https://i.pravatar.cc/150?u=d10","joinedDate":"2022-05-01"}
]


trips = []
fuel_records = []
maintenance_records = []
notifications = []
kpis = []

# -------------------------------
# Global variables
# -------------------------------

vehicle_clients: Dict[str, list[WebSocket]] = {}  # per vehicle
all_vehicle_clients: List[WebSocket] = []         # for /all
vehicle_lock = threading.Lock()

# Camera threads
camera_threads = {}

# -------------------------------
# FastAPI App
# -------------------------------

app = FastAPI(title="FleetPulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

API_PREFIX = "/api"

# -------------------------------
# REST Endpoints
# -------------------------------

@app.get(f"{API_PREFIX}/users", response_model=List[User])
def get_users():
    return users

@app.get(f"{API_PREFIX}/vehicles", response_model=List[Vehicle])
def get_vehicles():
    return vehicles

@app.get(f"{API_PREFIX}/drivers", response_model=List[Driver])
def get_drivers():
    return drivers

@app.get(f"{API_PREFIX}/trips", response_model=List[Trip])
def get_trips():
    return trips

@app.get(f"{API_PREFIX}/fuel-records", response_model=List[FuelRecord])
def get_fuel_records():
    return fuel_records

@app.get(f"{API_PREFIX}/maintenance-records", response_model=List[MaintenanceRecord])
def get_maintenance_records():
    return maintenance_records

@app.get(f"{API_PREFIX}/notifications", response_model=List[Notification])
def get_notifications():
    return notifications

@app.get(f"{API_PREFIX}/kpis", response_model=List[KPI])
def get_kpis():
    return kpis

@app.get(f"{API_PREFIX}/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow()}

# -------------------------------
# Camera Feed
# -------------------------------

def generate_frames(vehicle_id):
    cap = cv2.VideoCapture(0)
    while camera_threads.get(vehicle_id, False):
        success, frame = cap.read()
        if not success:
            break
        ret, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
    cap.release()

@app.get("/api/vehicle/{vehicle_id}/camera_feed")
def camera_feed(vehicle_id: str):
    camera_threads[vehicle_id] = True
    return StreamingResponse(generate_frames(vehicle_id), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/api/vehicle/{vehicle_id}/camera_feed/stop")
def stop_camera_feed(vehicle_id: str):
    camera_threads[vehicle_id] = False
    return {"status": "stopped", "vehicle_id": vehicle_id}


# Webhook endpoint to update truck location
@app.post("/api/vehicle/{vehicle_id}/update_location")
def update_vehicle_location(vehicle_id: str, update: VehicleLocationUpdate):
    with vehicle_lock:
        vehicle = next((v for v in vehicles if v["id"] == vehicle_id), None)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        vehicle["location"]["lat"] = update.lat
        vehicle["location"]["lng"] = update.lng
        if update.speed is not None:
            vehicle["speed"] = update.speed
        if update.fuelLevel is not None:
            vehicle["fuelLevel"] = update.fuelLevel

        # Optionally, update location name based on lat/lng (if you have a reverse geocode service)
        # vehicle["locationName"] = reverse_geocode(update.lat, update.lng)

    return {"status": "success", "vehicle_id": vehicle_id, "new_location": vehicle["location"]}
