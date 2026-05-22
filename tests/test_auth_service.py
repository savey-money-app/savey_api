from datetime import timedelta

from services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_round_trip():
    hashed_password = hash_password("not-a-real-secret")

    assert hashed_password != "not-a-real-secret"
    assert verify_password("not-a-real-secret", hashed_password)
    assert not verify_password("wrong", hashed_password)


def test_access_token_round_trip_and_invalid_token():
    token = create_access_token({"sub": "user-1"}, expires_delta=timedelta(minutes=1))

    assert decode_access_token(token)["sub"] == "user-1"
    assert decode_access_token("not-a-token") is None
