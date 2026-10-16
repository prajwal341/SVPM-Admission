import hashlib
import hmac
import json
import os
import secrets
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import APIException

from .models import OTPChallenge


class OTPDeliveryUnavailable(APIException):
    status_code = 503
    default_detail = "OTP delivery is not configured. Contact the admissions office."
    default_code = "otp_delivery_unavailable"


def _digest(challenge_id, channel, code):
    material = f"{challenge_id}:{channel}:{code}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), material, hashlib.sha256).hexdigest()


def _send_mobile_otp(mobile, code, purpose):
    provider = os.getenv("SMS_OTP_PROVIDER", "").strip().lower()
    if provider == "msg91":
        api_key = os.getenv("MSG91_AUTH_KEY", "").strip()
        template_id = os.getenv("MSG91_SMS_TEMPLATE_ID", "").strip()
        if not api_key or not template_id:
            raise OTPDeliveryUnavailable("MSG91 requires MSG91_AUTH_KEY and MSG91_SMS_TEMPLATE_ID in backend/.env.")
        international_mobile = mobile if mobile.startswith("91") and len(mobile) == 12 else f"91{mobile}"
        payload = {"template_id": template_id, "short_url": "0", "realTimeResponse": "1",
                   "recipients": [{"mobiles": international_mobile, "VAR1": code}]}
        request = urllib.request.Request("https://control.msg91.com/api/v5/flow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"authkey": api_key, "accept": "application/json", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                response_text = response.read().decode("utf-8", errors="replace")
                if not 200 <= response.status < 300:
                    raise OTPDeliveryUnavailable()
            result = json.loads(response_text) if response_text else {}
            result_text = json.dumps(result).lower()
            if any(marker in result_text for marker in ('"type":"error"', '"type": "error"', '"status": "error"')):
                raise OTPDeliveryUnavailable()
        except OTPDeliveryUnavailable:
            raise
        except Exception as exc:
            raise OTPDeliveryUnavailable() from exc
        return

    # Keep the generic webhook option for college-managed integrations.
    url = os.getenv("SMS_OTP_WEBHOOK_URL", "").strip()
    api_key = os.getenv("SMS_OTP_API_KEY", "").strip()
    if url and api_key and not settings.DEBUG:
        message = f"Your SVPM {purpose} verification code is {code}. It expires in 5 minutes. Do not share it."
        request = urllib.request.Request(url, data=json.dumps({"to": mobile, "message": message}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                if not 200 <= response.status < 300:
                    raise OTPDeliveryUnavailable()
        except Exception as exc:
            raise OTPDeliveryUnavailable() from exc
        return
    if settings.DEBUG:
        print(f"[SVPM DEV SMS] {mobile} | OTP: {code}")
        return
    raise OTPDeliveryUnavailable()
def issue_otp_pair(*, challenge_id, email, mobile, purpose):
    """Create short-lived one-time codes and send each through its configured channel."""
    now = timezone.now()
    email_code = f"{secrets.randbelow(1_000_000):06d}"
    sms_code = f"{secrets.randbelow(1_000_000):06d}"
    rows = [
        OTPChallenge(challenge_id=challenge_id, email=email, mobile=mobile, channel=OTPChallenge.Channel.EMAIL,
            purpose=purpose, code_digest=_digest(challenge_id, "EMAIL", email_code), expires_at=now + timedelta(minutes=5)),
        OTPChallenge(challenge_id=challenge_id, email=email, mobile=mobile, channel=OTPChallenge.Channel.SMS,
            purpose=purpose, code_digest=_digest(challenge_id, "SMS", sms_code), expires_at=now + timedelta(minutes=5)),
    ]
    OTPChallenge.objects.bulk_create(rows)
    try:
        send_mail(f"SVPM {purpose.replace('_', ' ').lower()} verification", f"Your verification code is {email_code}. It expires in 5 minutes. Do not share it.", None, [email], fail_silently=False)
    except Exception as exc:
        raise OTPDeliveryUnavailable() from exc
    _send_mobile_otp(mobile, sms_code, purpose.replace("_", " ").lower())


def verify_otp_pair(*, challenge_id, purpose, email_code, mobile_code):
    rows = list(OTPChallenge.objects.select_for_update().filter(challenge_id=challenge_id, purpose=purpose, used_at__isnull=True))
    if len(rows) != 2:
        return False
    supplied = {"EMAIL": str(email_code).strip(), "SMS": str(mobile_code).strip()}
    by_channel = {row.channel: row for row in rows}
    if set(by_channel) != {"EMAIL", "SMS"}:
        return False
    now = timezone.now()
    valid = True
    for channel, row in by_channel.items():
        if row.expires_at <= now or row.attempts >= 5:
            valid = False
            continue
        expected = _digest(challenge_id, channel, supplied[channel])
        if not hmac.compare_digest(row.code_digest, expected):
            row.attempts += 1
            row.save(update_fields=["attempts"])
            valid = False
    if not valid:
        return False
    for row in rows:
        row.used_at = now
        row.save(update_fields=["used_at"])
    return True
