import requests, re, json, time
from datetime import datetime
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

ACKO_URL = "https://www.acko.com/motororchestrator/api/v2/proposals"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MOBILE_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"
MOBILE = "9991577415"


def ts_to_date(ts):
    if not ts: return None
    try: return datetime.fromtimestamp(ts / 1000).strftime("%d-%m-%Y")
    except: return str(ts)


def scrape_vahanx(vnum):
    try:
        s = requests.Session()
        s.headers.update({'User-Agent': USER_AGENT})
        r = s.get(f'https://vahanx.in/rc-search/{vnum}', timeout=20)
        if r.status_code != 200: return {}
        text = r.text
        data = {}
        
        # Fields in the summary card: <div class="hrcd-cardbody">\n<p>VALUE</p>\n<span>LABEL</span>
        pairs = [
            ('owner_name', r'hrcd-cardbody">\s*<p>([^<]+)</p>\s*<span>Owner Name</span>'),
            ('address', r'hrcd-cardbody">\s*<p>([^<]+)</p>\s*<span>Address</span>'),
            ('rto_code', r'hrcd-cardbody">\s*<p>([^<]+)</p>\s*<span>Code</span>'),
            ('city', r'hrcd-cardbody">\s*<p>([^<]+)</p>\s*<span>City Name</span>'),
        ]
        
        for key, pat in pairs:
            m = re.search(pat, text, re.DOTALL)
            if m:
                data[key] = m.group(1).strip()
        
        # Fields in the detail cards: <span>LABEL</span>\n<p>VALUE</p>
        pairs2 = [
            ('registered_rto', r'<span[^>]*>Registered RTO</span>\s*<p[^>]*>([^<]+)'),
            ('manufacturer_vahanx', r'<span[^>]*>Model Name</span>\s*<p[^>]*>([^<]+)'),
            ('maker_model', r'<span[^>]*>Maker Model</span>\s*<p[^>]*>([^<]+)'),
            ('vehicle_class', r'<span[^>]*>Vehicle Class</span>\s*<p[^>]*>([^<]+)'),
            ('fuel_type_vahanx', r'<span[^>]*>Fuel Type</span>\s*<p[^>]*>([^<]+)'),
            ('fuel_norms', r'<span[^>]*>Fuel Norms</span>\s*<p[^>]*>([^<]+)'),
            ('chassis_number', r'<span[^>]*>Chassis Number</span>\s*<p[^>]*>([^<]+)'),
            ('engine_number', r'<span[^>]*>Engine Number</span>\s*<p[^>]*>([^<]+)'),
            ('registration_date', r'<span[^>]*>Registration Date</span>\s*<p[^>]*>([^<]+)'),
            ('vehicle_age', r'<span[^>]*>Vehicle Age</span>\s*<p[^>]*>([^<]+)'),
            ('fitness_upto', r'<span[^>]*>Fitness Upto</span>\s*<p[^>]*>([^<]+)'),
            ('tax_upto', r'<span[^>]*>Tax Upto</span>\s*<p[^>]*>([^<]+)'),
            ('puc_no', r'<span[^>]*>PUC No</span>\s*<p[^>]*>([^<]+)'),
            ('insurance_expiry_vahanx', r'<span[^>]*>Insurance Expiry</span>\s*<p[^>]*>([^<]+)'),
            ('insurance_no', r'<span[^>]*>Insurance No</span>\s*<p[^>]*>([^<]+)'),
            ('puc_upto', r'<span[^>]*>PUC Upto</span>\s*<p[^>]*>([^<]+)'),
            ('puc_expiry_in', r'<span[^>]*>PUC Expiry In</span>\s*<p[^>]*>([^<]+)'),
            ('insurance_upto', r'<span[^>]*>Insurance Upto</span>\s*<p[^>]*>([^<]+)'),
            ('insurance_expiry_in', r'<span[^>]*>Insurance Expiry In</span>\s*<p[^>]*>([^<]+)'),
            ('financer_name', r'<span[^>]*>Financer Name</span>\s*<p[^>]*>([^<]+)'),
            ('cubic_capacity', r'<span[^>]*>Cubic Capacity</span>\s*<p[^>]*>([^<]+)'),
            ('seating_capacity_vahanx', r'<span[^>]*>Seating Capacity</span>\s*<p[^>]*>([^<]+)'),
            ('permit_type', r'<span[^>]*>Permit Type</span>\s*<p[^>]*>([^<]+)'),
            ('blacklist_status', r'<span[^>]*>Blacklist Status</span>\s*<p[^>]*>([^<]+)'),
            ('noc_details', r'<span[^>]*>NOC Details</span>\s*<p[^>]*>([^<]+)'),
        ]
        
        for key, pat in pairs2:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                data[key] = m.group(1).strip()
        
        return data
    except:
        return {}


def query_vahandetails(vnum):
    try:
        headers = {
            'User-Agent': MOBILE_UA,
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://vahandetails.com',
            'Referer': 'https://vahandetails.com/',
        }
        r = requests.get(f'https://restapi.vahandetails.com/api/vehicles/search?rc_regn_no={vnum}', headers=headers, timeout=30)
        if r.status_code == 200:
            raw = r.json().get("data", {})
            rc = raw.get("rc_details", {})
            ins = raw.get("insurance", [{}])
            puc = raw.get("puc", [{}])
            if not rc: return {}
            ins_co = ins[0].get("insurance_company") if ins else None
            ins_no = ins[0].get("insurance_policy_no") if ins else None
            ins_upto = ins[0].get("insurance_valid_upto") if ins and ins[0].get("insurance_valid_upto") else None
            if ins_upto: ins_upto = ins_upto.replace("T00:00:00.000Z", "")
            puc_no = puc[0].get("pucc_no") if puc else None
            puc_upto = puc[0].get("pucc_valid_upto") if puc and puc[0].get("pucc_valid_upto") else None
            if puc_upto: puc_upto = puc_upto.replace("T00:00:00.000Z", "")
            reg_dt = rc.get("rc_regn_dt")
            if reg_dt: reg_dt = reg_dt.replace("T00:00:00.000Z", "")
            reg_up = rc.get("rc_regn_upto")
            if reg_up: reg_up = reg_up.replace("T00:00:00.000Z", "")
            fit_up = rc.get("rc_fit_upto")
            if fit_up: fit_up = fit_up.replace("T00:00:00.000Z", "")
            tax_up = rc.get("rc_tax_upto")
            if tax_up: tax_up = tax_up.replace("T00:00:00.000Z", "")
            purch = rc.get("rc_purchase_dt")
            if purch: purch = purch.replace("T00:00:00.000Z", "")
            return {
                "owner_name_vd": rc.get("rc_owner_name"),
                "color": rc.get("rc_color"),
                "maker_model_vd": rc.get("rc_maker_model"),
                "maker_desc": rc.get("rc_maker_desc"),
                "vehicle_class_vd": rc.get("rc_vh_class_desc"),
                "fuel_type_vd": rc.get("rc_fuel_desc"),
                "cubic_cap_vd": rc.get("rc_cubic_cap"),
                "seat_cap_vd": rc.get("rc_seat_cap"),
                "engine_number_vd": rc.get("rc_eng_no"),
                "chassis_number_vd": rc.get("rc_chasi_no"),
                "manufacturing_month_year": rc.get("rc_manu_month_yr"),
                "registration_date_vd": reg_dt,
                "registration_valid_upto": reg_up,
                "fitness_upto_vd": fit_up,
                "tax_upto_vd": tax_up,
                "purchase_date": purch,
                "rto_vd": rc.get("rc_registered_at"),
                "rc_status": rc.get("rc_status"),
                "address_vd": rc.get("rc_present_address"),
                "financer": rc.get("rc_financer"),
                "norms_desc": rc.get("rc_norms_desc"),
                "gvw": rc.get("rc_gvw"),
                "unladen_weight": rc.get("rc_unld_wt"),
                "wheelbase": rc.get("rc_wheelbase"),
                "sale_amount": rc.get("rc_sale_amt"),
                "body_type": rc.get("rc_body_type_desc"),
                "insurance_company_vd": ins_co,
                "insurance_policy_no": ins_no,
                "insurance_valid_upto_vd": ins_upto,
                "puc_no_vd": puc_no,
                "puc_valid_upto_vd": puc_upto,
                "is_rc_expired": raw.get("is_rc_expired"),
                "is_insurance_expired": raw.get("is_insurance_expired"),
                "is_puc_expired": raw.get("is_puc_expired"),
                "has_pending_challan": raw.get("has_pending_challan"),
                "pending_challan_count": raw.get("pending_challan_count"),
                "data_source_vd": rc.get("data_source"),
            }
    except Exception as e:
        import sys; print(f"[VD ERROR] {e}", file=sys.stderr)
    return {}


def query_acko(vnum):
    sess = requests.Session()
    sess.headers.update({"User-Agent": MOBILE_UA})
    sess.get("https://www.acko.com", timeout=10)
    
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
                    "owner_name_unmasked": data.get("user", {}).get("name"),
                    "manufacturer": v.get("make_name"),
                    "model": v.get("model_name"),
                    "variant": v.get("variant_name"),
                    "engine_number_unmasked": v.get("engine_number_unmasked"),
                    "chassis_number_unmasked": v.get("chassis_number_unmasked"),
                    "cc": v.get("cc"),
                    "seat_capacity": v.get("seating_capacity"),
                    "registration_date_acko": ts_to_date(v.get("registration_date")),
                    "registration_year": v.get("registration_year"),
                    "acko_insurance_company": prev.get("insurer_name"),
                    "acko_insurance_expiry": ts_to_date(prev.get("expiry_date")),
                }
        except:
            pass
    return {}


@app.route("/")
def home():
    return jsonify({"status": "running", "message": "Vehicle RC API (ACKO + VahanX + Fuel)"})


@app.route("/api/fuel", methods=["GET"])
def fuel():
    city = request.args.get("city", "").strip().lower()
    if not city:
        return jsonify({"status": "failed", "message": "Missing city"}), 400

    headers = {
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
    try:
        r = requests.get(f'https://api.motoinfo.app/nexus/v1/api/fuel/prices?city={city}', headers=headers, timeout=10)
        data = r.json()
        return jsonify({"status": "success", "city": city, "petrol": data.get("petrol"), "diesel": data.get("diesel")})
    except Exception as e:
        return jsonify({"status": "failed", "message": str(e)[:100]}), 502


@app.route("/api/vehicle", methods=["GET"])
def vehicle():
    vnum = request.args.get("vnum", "").strip().upper()
    if not vnum:
        return jsonify({"status": "failed", "message": "Missing vnum"}), 400

    acko = query_acko(vnum)
    vahanx = scrape_vahanx(vnum)
    vahandetails = query_vahandetails(vnum)

    if not acko and not vahanx and not vahandetails:
        return jsonify({"status": "failed", "message": "Vehicle not found"}), 404

    result = {"status": "success", "registration_number": vnum}
    result.update(acko)
    result.update(vahandetails)
    result.update(vahanx)
    if result.get("owner_name_unmasked"):
        result["name"] = result["owner_name_unmasked"]
    result["data_source"] = []
    if acko: result["data_source"].append("acko")
    if vahanx: result["data_source"].append("vahanx")
    if vahandetails: result["data_source"].append("vahandetails")

    for f in ["puc_no", "tax_upto_vd", "seat_cap_vd", "registration_date_acko",
              "registration_date_vd", "owner_name_vd",
              "maker_model_vd", "insurance_no", "fuel_type_vd",
              "engine_number_vd", "chassis_number_vd"]:
        result.pop(f, None)

    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
