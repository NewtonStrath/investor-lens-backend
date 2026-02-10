import time
import random
import requests
import asyncio

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

VEHICLE_IDS = [v["id"] for v in vehicles]

while True:
    for vid in VEHICLE_IDS:
        lat = -1.2921 + random.uniform(-0.01, 0.01)
        lng = 36.8219 + random.uniform(-0.01, 0.01)
        speed = random.randint(50, 80)
        fuel = random.randint(100, 150)
        requests.post(f"http://127.0.0.1:8000/api/vehicle/{vid}/update_location", json={
            "lat": lat,
            "lng": lng,
            "speed": speed,
            "fuelLevel": fuel
        })
        print(f"Sending update for {vid}")
    time.sleep(5)