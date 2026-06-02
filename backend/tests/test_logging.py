from app.core.logging import scrub_sensitive


def test_scrub_masks_phone_gps_email_token():
    event = {
        "phone": "+919876543210",
        "lat": 28.612894, "lng": 77.229446,
        "email": "ramesh@school.com",
        "url": "/socket?token=abc.def.ghi&x=1",
        "password": "hunter2",
    }
    out = scrub_sensitive(None, None, dict(event))
    assert out["phone"].endswith("3210") and out["phone"].startswith("***")
    assert out["lat"] == 28.61 and out["lng"] == 77.23      # rounded to 2dp
    assert out["email"] == "***@school.com"
    assert "token=" not in out["url"] or out["url"].split("token=")[1].startswith("***")
    assert out["password"] == "***"
