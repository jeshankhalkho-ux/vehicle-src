# vehicle-api (production)
from flask import Flask, request, jsonify
import requests
import logging
import re
import time
import os
from datetime import datetime
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
CORS(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["30 per minute"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SMC Insurance (working) ---
SMC_URL = "https://www.smcinsurance.com/central/centralcall/CallReqWithHeader"
SMC_HEADERS = {
    'User-Agent': "Mozilla/5.0 (Linux; Android 16; CPH2729 Build/BP2A.250605.015) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'Content-Type': "application/json",
    'sec-ch-ua-platform': "\"Android\"",
    'sec-ch-ua': "\"Not;A=Brand\";v=\"8\", \"Chromium\";v=\"150\", \"Android WebView\";v=\"150\"",
    'sec-ch-ua-mobile': "?1",
    'origin': "https://www.smcinsurance.com",
    'sec-fetch-site': "same-origin",
    'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'referer': "https://www.smcinsurance.com/",
    'accept-language': "en-IN,en-US;q=0.9,en;q=0.8",
    'priority': "u=1, i"
}

SMC_SESSION = requests.Session()
SMC_SESSION.headers.update(SMC_HEADERS)
try:
    SMC_SESSION.get("https://www.smcinsurance.com/", timeout=15)
except:
    pass

# --- ACKO ---
ACKO_URL = "https://www.acko.com/motororchestrator/api/v2/proposals"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MOBILE_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"
MOBILE = "9991577415"

# --- vahandetails.com ---
VD_HEADERS = {
    'User-Agent': MOBILE_UA,
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://vahandetails.com',
    'Referer': 'https://vahandetails.com/',
}

# --- Fuel ---
FUEL_HEADERS = {
    'x-platform': 'web',
    'x-device-fingerprint': 'ab00c0e8996aca383680b36068354328',
    'x-visit-count': '1',
    'x-timestamp': str(int(time.time() * 1000)),
    'x-device-type': 'mobile/linux/chrome',
    'x-app-version': '1',
    'User-Agent': USER_AGENT,
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://motoinfo.app',
    'Referer': 'https://motoinfo.app/',
}

# --- Shared Session Pool ---
SESSION_POOL = {}


def get_session(key: str, headers: dict = None) -> requests.Session:
    """Get or create a persistent session for connection pooling."""
    if key not in SESSION_POOL:
        sess = requests.Session()
        if headers:
            sess.headers.update(headers)
        SESSION_POOL[key] = sess
    return SESSION_POOL[key]


def ts_to_date(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000).strftime("%d-%m-%Y")
    except:
        return str(ts)


def iso(d):
    return d.replace("T00:00:00.000Z", "") if d else None


# --- Source: SMC Insurance (NEW - working) ---
def query_smc(vnum):
    payload = {"URL": "GetVaahanDetailsByVehicleNo", "Props": [vnum], "Token": ""}
    try:
        resp = SMC_SESSION.post(SMC_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rc = data.get("response", {})
        if not rc:
            return {}
        return {
            "source": "smc",
            "owner_name": rc.get("owner"),
            "father_name": rc.get("ownerFatherName"),
            "manufacturer": rc.get("manufacturer"),
            "model": rc.get("vehicle"),
            "variant": rc.get("variant"),
            "vehicle_class": rc.get("vehicleClass"),
            "fuel_type": rc.get("fuelType"),
            "cc": rc.get("cubicCapacity"),
            "seating_capacity": rc.get("seatCapacity"),
            "engine_number": rc.get("engine"),
            "chassis_number": rc.get("chassis"),
            "registration_date": rc.get("regDate"),
            "registration_valid_upto": rc.get("eDate"),
            "insurance_company": rc.get("insuranceCompanyName"),
            "insurance_policy_no": rc.get("insurancePolicyNumber"),
            "insurance_valid_upto": rc.get("insuranceUpto"),
            "rto_code": rc.get("rtoCode"),
            "rto_name": rc.get("regAuthority"),
            "address": rc.get("presentAddress"),
            "financer": rc.get("financerName"),
            "is_commercial": rc.get("isCommercial"),
            "puc_no": rc.get("puccNumber"),
            "puc_valid_upto": rc.get("puccValidUpto"),
        }
    except Exception as e:
        logger.warning(f"SMC failed for {vnum}: {e}")
        return {}


# --- Source: VahanX (HTML scraping) ---
def scrape_vahanx(vnum):
    sess = get_session("vahanx", {"User-Agent": USER_AGENT})
    try:
        r = sess.get(f"https://vahanx.in/rc-search/{vnum}", timeout=20)
        if r.status_code != 200:
            return {}
        text = r.text

        pairs = [
            ("owner_name", r"hrcd-cardbody\">\s*<p>([^<]+)</p>\s*<span>Owner Name</span>"),
            ("address", r"hrcd-cardbody\">\s*<p>([^<]+)</p>\s*<span>Address</span>"),
            ("rto_code", r"hrcd-cardbody\">\s*<p>([^<]+)</p>\s*<span>Code</span>"),
            ("city", r"hrcd-cardbody\">\s*<p>([^<]+)</p>\s*<span>City Name</span>"),
        ]
        data = {"source": "vahanx"}
        for key, pat in pairs:
            m = re.search(pat, text, re.DOTALL)
            if m:
                data[key] = m.group(1).strip()

        pairs2 = [
            ("registered_rto", r"<span[^>]*>Registered RTO</span>\s*<p[^>]*>([^<]+)"),
            ("manufacturer_vahanx", r"<span[^>]*>Model Name</span>\s*<p[^>]*>([^<]+)"),
            ("maker_model", r"<span[^>]*>Maker Model</span>\s*<p[^>]*>([^<]+)"),
            ("vehicle_class", r"<span[^>]*>Vehicle Class</span>\s*<p[^>]*>([^<]+)"),
            ("fuel_type_vahanx", r"<span[^>]*>Fuel Type</span>\s*<p[^>]*>([^<]+)"),
            ("fuel_norms", r"<span[^>]*>Fuel Norms</span>\s*<p[^>]*>([^<]+)"),
            ("chassis_number_masked", r"<span[^>]*>Chassis Number</span>\s*<p[^>]*>([^<]+)"),
            ("engine_number_masked", r"<span[^>]*>Engine Number</span>\s*<p[^>]*>([^<]+)"),
            ("registration_date", r"<span[^>]*>Registration Date</span>\s*<p[^>]*>([^<]+)"),
            ("vehicle_age", r"<span[^>]*>Vehicle Age</span>\s*<p[^>]*>([^<]+)"),
            ("fitness_upto", r"<span[^>]*>Fitness Upto</span>\s*<p[^>]*>([^<]+)"),
            ("tax_upto", r"<span[^>]*>Tax Upto</span>\s*<p[^>]*>([^<]+)"),
            ("puc_no", r"<span[^>]*>PUC No</span>\s*<p[^>]*>([^<]+)"),
            ("insurance_expiry_vahanx", r"<span[^>]*>Insurance Expiry</span>\s*<p[^>]*>([^<]+)"),
            ("insurance_company_vahanx", r"<span[^>]*>Insurance Company</span>\s*<p[^>]*>([^<]+)"),
            ("insurance_no", r"<span[^>]*>Insurance No</span>\s*<p[^>]*>([^<]+)"),
            ("puc_upto", r"<span[^>]*>PUC Upto</span>\s*<p[^>]*>([^<]+)"),
            ("puc_expiry_in", r"<span[^>]*>PUC Expiry In</span>\s*<p[^>]*>([^<]+)"),
            ("insurance_upto", r"<span[^>]*>Insurance Upto</span>\s*<p[^>]*>([^<]+)"),
            ("insurance_expiry_in", r"<span[^>]*>Insurance Expiry In</span>\s*<p[^>]*>([^<]+)"),
            ("financer_name", r"<span[^>]*>Financer Name</span>\s*<p[^>]*>([^<]+)"),
            ("cubic_capacity", r"<span[^>]*>Cubic Capacity</span>\s*<p[^>]*>([^<]+)"),
            ("seating_capacity_vahanx", r"<span[^>]*>Seating Capacity</span>\s*<p[^>]*>([^<]+)"),
            ("permit_type", r"<span[^>]*>Permit Type</span>\s*<p[^>]*>([^<]+)"),
            ("blacklist_status", r"<span[^>]*>Blacklist Status</span>\s*<p[^>]*>([^<]+)"),
            ("noc_details", r"<span[^>]*>NOC Details</span>\s*<p[^>]*>([^<]+)"),
        ]
        for key, pat in pairs2:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                data[key] = m.group(1).strip()

        return data
    except Exception as e:
        logger.warning(f"VahanX failed for {vnum}: {e}")
        return {}


# --- Source: vahandetails.com API ---
def query_vahandetails(vnum):
    sess = get_session("vahandetails", VD_HEADERS)
    try:
        r = sess.get(f"https://restapi.vahandetails.com/api/vehicles/search?rc_regn_no={vnum}", timeout=30)
        if r.status_code != 200:
            return {}
        raw = r.json().get("data", {})
        rc = raw.get("rc_details", {})
        ins = raw.get("insurance", [{}])
        puc = raw.get("puc", [{}])
        if not rc:
            return {}

        ins_co = ins[0].get("insurance_company") if ins else None
        ins_no = ins[0].get("insurance_policy_no") if ins else None
        ins_up = iso(ins[0].get("insurance_valid_upto")) if ins and ins[0].get("insurance_valid_upto") else None
        pu_no = puc[0].get("pucc_no") if puc else None
        pu_up = iso(puc[0].get("pucc_valid_upto")) if puc and puc[0].get("pucc_valid_upto") else None

        return {
            "source": "vahandetails",
            "owner_name": rc.get("rc_owner_name"),
            "color": rc.get("rc_color"),
            "maker_model": rc.get("rc_maker_model"),
            "maker_desc": rc.get("rc_maker_desc"),
            "vehicle_class": rc.get("rc_vh_class_desc"),
            "fuel_type": rc.get("rc_fuel_desc"),
            "cubic_capacity": rc.get("rc_cubic_cap"),
            "seating_capacity": rc.get("rc_seat_cap"),
            "engine_number": rc.get("rc_eng_no"),
            "chassis_number": rc.get("rc_chasi_no"),
            "manufacturing_month_year": rc.get("rc_manu_month_yr"),
            "registration_date": iso(rc.get("rc_regn_dt")),
            "registration_valid_upto": iso(rc.get("rc_regn_upto")),
            "fitness_upto": iso(rc.get("rc_fit_upto")),
            "tax_upto": iso(rc.get("rc_tax_upto")),
            "purchase_date": iso(rc.get("rc_purchase_dt")),
            "rto": rc.get("rc_registered_at"),
            "rc_status": rc.get("rc_status"),
            "address": rc.get("rc_present_address"),
            "financer": rc.get("rc_financer"),
            "norms_desc": rc.get("rc_norms_desc"),
            "gvw": rc.get("rc_gvw"),
            "unladen_weight": rc.get("rc_unld_wt"),
            "wheelbase": rc.get("rc_wheelbase"),
            "sale_amount": rc.get("rc_sale_amt"),
            "body_type": rc.get("rc_body_type_desc"),
            "insurance_company": ins_co,
            "insurance_policy_no": ins_no,
            "insurance_valid_upto": ins_up,
            "puc_no": pu_no,
            "puc_valid_upto": pu_up,
            "is_rc_expired": raw.get("is_rc_expired"),
            "is_insurance_expired": raw.get("is_insurance_expired"),
            "is_puc_expired": raw.get("is_puc_expired"),
            "has_pending_challan": raw.get("has_pending_challan"),
            "pending_challan_count": raw.get("pending_challan_count"),
        }
    except Exception as e:
        logger.warning(f"vahandetails failed for {vnum}: {e}")
        return {}


# --- Source: ACKO VehicleInfo ---
def query_acko_vehicleinfo(vnum):
    try:
        r = requests.get(f"https://www.acko.com/api/app/vehicleInfo/?regNo={vnum}", headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Origin": "https://www.acko.com",
            "Referer": "https://www.acko.com/",
        }, timeout=20)
        if r.status_code == 200:
            d = r.json()
            if d.get("registration_number"):
                return {
                    "source": "acko_vehicleinfo",
                    "owner_name": d.get("owner_name"),
                    "vehicle_make": d.get("db_make_name"),
                    "vehicle_model": d.get("db_model_name"),
                    "vehicle_variant": d.get("model_name"),
                    "vehicle_type": d.get("vehicle_type_v2"),
                    "fuel_type": d.get("fuel_type"),
                    "policy_expiry_detail": d.get("previous_policy_expiry_detail"),
                    "variant_id": d.get("variant_id"),
                }
    except Exception as e:
        logger.warning(f"ACKO VehicleInfo failed for {vnum}: {e}")
    return {}


# --- Source: ACKO (proposal) ---
def query_acko(vnum):
    sess = get_session("acko", {"User-Agent": MOBILE_UA})
    try:
        sess.get("https://www.acko.com", timeout=10)
    except:
        pass

    for product in ["bike", "car"]:
        payload = {
            "registration_number": vnum,
            "mobile_no": MOBILE,
            "origin": f"acko_{product}",
            "product": product,
            "is_new": False,
        }
        try:
            r = sess.post(ACKO_URL, json=payload, headers={
                "Content-Type": "application/json",
                "Origin": "https://www.acko.com",
                "Referer": f"https://www.acko.com/gi/lp/{product}-insurance/new/",
            }, timeout=15)
            data = r.json()
            v = data.get("vehicle", {})
            if v.get("make_name"):
                prev = v.get("previous_policy", {})
                return {
                    "source": "acko",
                    "owner_name": data.get("user", {}).get("name"),
                    "manufacturer": v.get("make_name"),
                    "model": v.get("model_name"),
                    "variant": v.get("variant_name"),
                    "engine_number": v.get("engine_number_unmasked"),
                    "chassis_number": v.get("chassis_number_unmasked"),
                    "cc": v.get("cc"),
                    "seating_capacity": v.get("seating_capacity"),
                    "registration_date": ts_to_date(v.get("registration_date")),
                    "registration_year": v.get("registration_year"),
                    "insurance_company": prev.get("insurer_name"),
                    "insurance_expiry": ts_to_date(prev.get("expiry_date")),
                }
        except Exception as e:
            logger.debug(f"ACKO {product} failed for {vnum}: {e}")
    return {}


# --- Source: Fuel prices ---
def query_fuel(city):
    headers = FUEL_HEADERS.copy()
    headers['x-timestamp'] = str(int(time.time() * 1000))
    try:
        r = requests.get(f"https://api.motoinfo.app/nexus/v1/api/fuel/prices?city={city}", headers=headers, timeout=10)
        data = r.json()
        return {"city": city, "petrol": data.get("petrol"), "diesel": data.get("diesel")}
    except Exception as e:
        logger.warning(f"Fuel failed for {city}: {e}")
        return {"error": str(e)[:100]}


# --- Merge helper ---
def merge_results(*results):
    """Merge multiple result dicts, preferring non-empty values."""
    merged = {}
    sources = []
    for r in results:
        if r and isinstance(r, dict):
            src = r.pop("source", None)
            if src:
                sources.append(src)
            for k, v in r.items():
                if v not in (None, "", [], {}) and k not in merged:
                    merged[k] = v
    if sources:
        merged["data_sources"] = sources
    return merged


# --- Routes ---
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "Vehicle RC API - Multi-source (SMC, ACKO, VahanX, vahandetails, Fuel)",
        "endpoints": {
            "vehicle": "GET /api/vehicle?vnum=MH12AB1234",
            "fuel": "GET /api/fuel?city=delhi",
            "smc_only": "GET /api/smc?vnum=MH12AB1234",
            "health": "GET /health"
        },
        "rate_limit": "10 requests/minute per IP"
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "services": {
            "smc": True,
            "acko": True,
            "vahanx": True,
            "vahandetails": True,
            "fuel": True
        }
    })


@app.route("/api/vehicle", methods=["GET"])
@limiter.limit("10 per minute")
def vehicle():
    vnum = request.args.get("vnum", "").strip().upper()
    if not vnum:
        return jsonify({"status": "failed", "message": "Missing vnum parameter"}), 400

    # Query all sources in parallel
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            "smc": executor.submit(query_smc, vnum),
            "acko": executor.submit(query_acko, vnum),
            "acko_vi": executor.submit(query_acko_vehicleinfo, vnum),
            "vahanx": executor.submit(scrape_vahanx, vnum),
            "vahandetails": executor.submit(query_vahandetails, vnum),
        }
        results = {k: f.result() for k, f in futures.items()}

    # Check if any source succeeded
    if not any(results.values()):
        return jsonify({"status": "failed", "message": "Vehicle not found in any source"}), 404

    # Merge results
    merged = merge_results(
        results["smc"],
        results["acko"],
        results["acko_vi"],
        results["vahanx"],
        results["vahandetails"],
    )
    merged["registration_number"] = vnum
    merged["status"] = "success"

    return jsonify(merged)


@app.route("/api/smc", methods=["GET"])
@limiter.limit("10 per minute")
def smc_only():
    vnum = request.args.get("vnum", "").strip().upper()
    if not vnum:
        return jsonify({"status": "failed", "message": "Missing vnum"}), 400
    data = query_smc(vnum)
    if not data:
        return jsonify({"status": "failed", "message": "Not found via SMC"}), 404
    data["registration_number"] = vnum
    data["status"] = "success"
    return jsonify(data)


@app.route("/api/fuel", methods=["GET"])
@limiter.limit("30 per minute")
def fuel():
    city = request.args.get("city", "").strip().lower()
    if not city:
        return jsonify({"status": "failed", "message": "Missing city"}), 400
    data = query_fuel(city)
    if "error" in data:
        return jsonify({"status": "failed", "message": data["error"]}), 502
    return jsonify({"status": "success", **data})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)