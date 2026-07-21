from flask import Flask, request, jsonify
import requests
from datetime import datetime
import os

app = Flask(__name__)

ACKO_URL = "https://www.acko.com/motororchestrator/api/v2/proposals"
USER_AGENT = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"
MOBILE = "9991577415"


def ts_to_date(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000).strftime("%d-%m-%Y")
    except:
        return str(ts)


def fetch_from_acko(vnum):
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
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
            r = sess.post(
                ACKO_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://www.acko.com",
                    "Referer": f"https://www.acko.com/gi/lp/{product}-insurance/new/",
                },
                timeout=15,
            )
            data = r.json()
            v = data.get("vehicle", {})
            if v.get("make_name"):
                prev = v.get("previous_policy", {})
                return {
                    "status": "success",
                    "registration_number": v.get("registration_number"),
                    "owner_name": data.get("user", {}).get("name"),
                    "manufacturer": v.get("make_name"),
                    "model": v.get("model_name"),
                    "variant": v.get("variant_name"),
                    "fuel_type": v.get("fuel_type"),
                    "cubic_cc": v.get("cc"),
                    "seat_capacity": v.get("seating_capacity"),
                    "engine_number": v.get("engine_number_unmasked"),
                    "chassis_number": v.get("chassis_number_unmasked"),
                    "registration_date": ts_to_date(v.get("registration_date")),
                    "manufacturing_year": v.get("registration_year"),
                    "insurance_company": prev.get("insurer_name"),
                    "insurance_valid_upto": ts_to_date(prev.get("expiry_date")),
                }
        except Exception as e:
            return {"status": "failed", "message": f"ACKO: {str(e)[:100]}"}
    return None


@app.route("/")
def home():
    return jsonify({"status": "running", "message": "Vehicle RC API"})


@app.route("/api/vehicle", methods=["GET"])
def vehicle():
    vnum = request.args.get("vnum", "").strip().upper()
    if not vnum:
        return jsonify({"status": "failed", "message": "Missing vnum"}), 400

    result = fetch_from_acko(vnum)
    if result and result.get("status") == "success":
        return jsonify(result)

    return jsonify({"status": "failed", "message": "Vehicle not found"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
