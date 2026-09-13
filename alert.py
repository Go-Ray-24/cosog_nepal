import os
import smtplib
import math
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SENDER = os.getenv("EMAIL_SENDER")
PASSWORD = os.getenv("EMAIL_PASSWORD", "").replace(" ", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the Great Circle distance (in kilometers) between two lat/lon points."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def send_email(recipient: str, subject: str, body: str) -> None:
    if not SENDER or not PASSWORD:
        raise RuntimeError("Set EMAIL_SENDER and EMAIL_PASSWORD in environment variables.")

    message = EmailMessage()
    message["From"] = SENDER
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SENDER, PASSWORD)
        smtp.send_message(message)


def dispatch_nearest_authority_alert(fires: list, communities: list) -> dict:
    """Finds the single nearest authority to any detected fire and sends an alert email."""
    if not fires or not communities:
        return {"status": "error", "message": "No fires or community data provided."}

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

            dist = haversine_distance(c_lat, c_lon, f_lat, f_lon)
            if dist < min_distance_km:
                min_distance_km = dist
                nearest_community = comm

    if not nearest_community or not nearest_community.get("email"):
        return {"status": "error", "message": "No valid nearest authority with email found."}

    name = nearest_community.get("name", "Unknown Zone")
    district = nearest_community.get("district", "Unknown District")
    email = nearest_community.get("email")

    subject = f"🚨 URGENT: Forest Fire Warning Near {name} ({district})"
    body = (
        f"FOREST FIRE EMERGENCY ALERT - NEAREST AUTHORITY NOTIFICATION\n"
        f"--------------------------------------------------\n"
        f"Nearest Station: {name}\n"
        f"District: {district}\n"
        f"Distance to Closest Fire: ~{min_distance_km:.2f} km\n"
        f"Total Active Detections: {len(fires)} Hotspot(s) in Geo-Fence\n\n"
        f"You are receiving this alert as the nearest registered authority. "
        f"Please deploy inspection teams immediately.\n\n"
        f"-- Nepal Forest Fire Early Warning System"
    )

    try:
        send_email(email, subject, body)
        print(f"[Nearest Alert Sent]: {name} ({min_distance_km:.2f} km away) <{email}>")
        return {
            "status": "success",
            "sent_count": 1,
            "recipient": {
                "name": name,
                "district": district,
                "email": email,
                "distance_km": round(min_distance_km, 2)
            }
        }
    except Exception as e:
        print(f"[Nearest Alert Failed]: {name} <{email}> - Error: {e}")
        return {"status": "error", "message": f"Failed sending to {email}: {e}"}