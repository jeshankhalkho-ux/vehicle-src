import requests, json

# 1. Try UMANG onorc API with various endpoints
print("=== UMANG onorc API ===")
base = "https://apigw.umangapp.in/onorcApi/ws1/"
headers = {
    "Content-Type": "application/json",
    "User-Agent": "okhttp/4.12.0",
    "Accept": "application/json"
}

# Try vehicle search endpoints
vnum = "JH05CK2458"
endpoints = {
    "searchVehicle": {"vehicleNo": vnum},
    "getVehicleDetails": {"regNo": vnum},
    "vehicleDetails": {"registrationNo": vnum},
    "rcDetails": {"vehicleNo": vnum},
    "getRcDetails": {"rcNumber": vnum},
    "fetchRC": {"regNumber": vnum},
    "vahanSearch": {"registrationNumber": vnum},
    "getRC": {"regNo": vnum},
    "search": {"vehicleno": vnum},
}

for ep, payload in endpoints.items():
    try:
        r = requests.post(base + ep, json=payload, headers=headers, timeout=10)
        print(f"[{r.status_code}] {ep}: {r.text[:300]}")
    except Exception as e:
        print(f"[ERR] {ep}: {e}")

# Try without ws1 prefix
base2 = "https://apigw.umangapp.in/onorcApi/"
for ep in ["getRcByRegNo", "fetchRc", "rc/vehicle", "vehicle"]:
    try:
        r = requests.post(base2 + ep, json={"regNo": vnum}, headers=headers, timeout=10)
        if r.status_code != 403:
            print(f"[{r.status_code}] {base2 + ep}: {r.text[:200]}")
    except:
        pass

# 2. Check mParivahan API
print("\n=== mParivahan API ===")
mparivahan_base = "https://mparivahan.parivahan.gov.in/"

# Try common endpoints
paths = [
    "api/rc/vehicle",
    "api/vahan/rc",
    "vahan/rc/details",
    "rc/details",
    "api/v1/rc",
]
for path in paths:
    try:
        r = requests.get(mparivahan_base + path, params={"regn_no": vnum}, timeout=10)
        print(f"[{r.status_code}] {path}: {r.text[:200]}")
    except Exception as e:
        print(f"[ERR] {path}: {e}")

# 3. Test vehicle-info directory
print("\n=== vehicle-info project ===")
try:
    r = requests.get("https://vehicle-info.vercel.app/", timeout=10)
    print(f"[{r.status_code}] vehicle-info: {r.text[:200]}")
except Exception as e:
    print(f"[ERR] vehicle-info: {e}")
