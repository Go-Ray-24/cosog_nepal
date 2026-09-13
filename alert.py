import os
import math
import requests

MAILERSEND_API_TOKEN=os.getenv("MAILERSEND_API_TOKEN", "mlsn.314596841f69228e5b8f265d61fb0d95915a1191c5c4a52947c926d5555811db")
MAILERSEND_FROM_EMAIL=os.getenv("MAILERSEND_FROM_EMAIL", "MS_141c8s@test-r9084zvmzmvgw63d.mlsender.net")
MAILERSEND_PASSWORD=os.getenv("MAILERSEND_PASSWORD", "mssp.IndV63X.x2p0347dr6k4zdrn.Fo1H3pJ")
MAILERSEND_FROM_NAME=os.getenv("MAILERSEND_FROM_NAME", "Nepal Forest Fire Early Warning System")
MAILERSEND_PORT=os.getenv("MAILERSEND_PORT", 587)

MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the Great Circle distance in kilometers."""
    R = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def send_email(recipient: str, subject: str, body: str) -> None:
    """
    Send an email through MailerSend Email API.

    This uses HTTPS instead of SMTP, so it works with
    Render Free's SMTP restrictions.
    """

    if not MAILERSEND_API_TOKEN:
        raise RuntimeError(
            "MAILERSEND_API_TOKEN is not configured."
        )

    if not MAILERSEND_FROM_EMAIL:
        raise RuntimeError(
            "MAILERSEND_FROM_EMAIL is not configured."
        )

    headers = {
        "Authorization": f"Bearer {MAILERSEND_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "from": {
            "email": MAILERSEND_FROM_EMAIL,
            "name": MAILERSEND_FROM_NAME,
        },
        "to": [
            {
                "email": recipient,
            }
        ],
        "subject": subject,
        "text": body,
    }

    try:
        response = requests.post(
            MAILERSEND_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code not in (200, 202):
            raise RuntimeError(
                f"MailerSend API error "
                f"{response.status_code}: {response.text}"
            )

        print(
            f"[Email Sent] {recipient} | "
            f"MailerSend status: {response.status_code}"
        )

    except requests.RequestException as e:
        raise RuntimeError(
            f"Failed connecting to MailerSend: {e}"
        )


def dispatch_nearest_authority_alert(
    fires: list,
    communities: list
) -> dict:
    """
    Finds the single nearest authority to any detected fire
    and sends an alert email.
    """

    if not fires or not communities:
        return {
            "status": "error",
            "message": "No fires or community data provided."
        }

    nearest_community = None
    min_distance_km = float("inf")

    # Find community with shortest distance to any fire point
    for comm in communities:

        c_lat = comm.get("latitude")
        c_lon = comm.get("longitude")

        if c_lat is None or c_lon is None:
            continue

        for fire in fires:

            f_lat = fire.get("latitude")
            f_lon = fire.get("longitude")

            if f_lat is None or f_lon is None:
                continue

            dist = haversine_distance(
                c_lat,
                c_lon,
                f_lat,
                f_lon
            )

            if dist < min_distance_km:
                min_distance_km = dist
                nearest_community = comm

    if not nearest_community:
        return {
            "status": "error",
            "message": "No valid nearest authority found."
        }

    if not nearest_community.get("email"):
        return {
            "status": "error",
            "message": "Nearest authority does not have an email."
        }

    name = nearest_community.get(
        "name",
        "Unknown Zone"
    )

    district = nearest_community.get(
        "district",
        "Unknown District"
    )

    email = nearest_community.get("email")

    subject = (
        f"🚨 URGENT: Forest Fire Warning Near "
        f"{name} ({district})"
    )

    body = (
        "FOREST FIRE EMERGENCY ALERT - "
        "NEAREST AUTHORITY NOTIFICATION\n"
        "--------------------------------------------------\n"
        f"Nearest Station: {name}\n"
        f"District: {district}\n"
        f"Distance to Closest Fire: "
        f"~{min_distance_km:.2f} km\n"
        f"Total Active Detections: "
        f"{len(fires)} Hotspot(s) in Geo-Fence\n\n"
        "You are receiving this alert as the nearest "
        "registered authority. Please deploy inspection "
        "teams immediately.\n\n"
        "-- Nepal Forest Fire Early Warning System"
    )

    try:

        send_email(
            recipient=email,
            subject=subject,
            body=body
        )

        print(
            f"[Nearest Alert Sent]: "
            f"{name} ({min_distance_km:.2f} km away) "
            f"<{email}>"
        )

        return {
            "status": "success",
            "sent_count": 1,
            "recipient": {
                "name": name,
                "district": district,
                "email": email,
                "distance_km": round(
                    min_distance_km,
                    2
                )
            }
        }

    except Exception as e:

        print(
            f"[Nearest Alert Failed]: "
            f"{name} <{email}> - Error: {e}"
        )

        return {
            "status": "error",
            "message": f"Failed sending to {email}: {e}"
        }