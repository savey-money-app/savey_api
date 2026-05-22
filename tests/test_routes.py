from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile

from models.transaction import TransactionType
from routes.v1 import categories, files, transactions, users
from schemas.category import CategoryCreate, CategoryUpdate
from schemas.transaction import TransactionCreate, TransactionUpdate, UserBalance
from schemas.user import UserUpdate


def balance():
    return UserBalance(
        balance=15,
        monthly_spending=5,
        monthly_limit=100,
        daily_spending=2,
        daily_limit=10,
    )


def user(user_id=None):
    now = datetime.utcnow()
    return SimpleNamespace(
        id=user_id or uuid4(),
        email="person@example.com",
        full_name="Person",
        currency="KZT",
        preferred_language="en",
        monthly_limit=100,
        daily_limit=10,
        created_at=now,
        updated_at=now,
    )


def category(category_id=None):
    return SimpleNamespace(id=category_id or uuid4(), title="Food")


def tx_response(cat):
    now = datetime.utcnow()
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        category_id=cat.id,
        category=SimpleNamespace(
            id=cat.id,
            title=cat.title,
            title_ru=None,
            created_at=now,
            updated_at=now,
        ),
        amount=Decimal("10"),
        description="Meal",
        transaction_type=TransactionType.EXPENSE,
        date=date(2026, 5, 22),
        created_at=now,
        updated_at=now,
    )


def create_tx(category_id):
    return TransactionCreate(
        amount=Decimal("10"),
        category_id=category_id,
        description="Meal",
        transaction_type=TransactionType.EXPENSE,
        date=date(2026, 5, 22),
    )


def test_category_routes(monkeypatch):
    item = category()
    monkeypatch.setattr(categories, "get_all_categories", lambda _db: [item])
    assert categories.list_categories("user", None) == [item]
    monkeypatch.setattr(categories, "get_category_by_id", lambda *_args: item)
    assert categories.get_category("id", "user", None) is item
    monkeypatch.setattr(categories, "get_category_by_id", lambda *_args: None)
    with pytest.raises(HTTPException) as missing:
        categories.get_category("id", "user", None)
    assert missing.value.status_code == 404

    payload = CategoryCreate(title="Food")
    monkeypatch.setattr(categories, "get_category_by_title", lambda *_args: item)
    with pytest.raises(HTTPException, match="already"):
        categories.create_new_category(payload, "user", None)
    monkeypatch.setattr(categories, "get_category_by_title", lambda *_args: None)
    monkeypatch.setattr(categories, "create_category", lambda _db, value: value)
    assert categories.create_new_category(payload, "user", None) == payload

    other = category()
    monkeypatch.setattr(categories, "get_category_by_title", lambda *_args: other)
    with pytest.raises(HTTPException, match="already"):
        categories.update_existing_category("different", CategoryUpdate(title="Food"), "user", None)
    monkeypatch.setattr(categories, "get_category_by_title", lambda *_args: None)
    monkeypatch.setattr(categories, "update_category", lambda *_args: item)
    assert categories.update_existing_category(str(item.id), CategoryUpdate(title="Food"), "user", None) is item
    monkeypatch.setattr(categories, "update_category", lambda *_args: None)
    with pytest.raises(HTTPException) as update_missing:
        categories.update_existing_category("missing", CategoryUpdate(title="Food"), "user", None)
    assert update_missing.value.status_code == 404

    monkeypatch.setattr(categories, "delete_category", lambda *_args: True)
    assert categories.delete_existing_category("id", "user", None) is None
    monkeypatch.setattr(categories, "delete_category", lambda *_args: False)
    with pytest.raises(HTTPException) as delete_missing:
        categories.delete_existing_category("id", "user", None)
    assert delete_missing.value.status_code == 400


def test_user_routes(monkeypatch):
    item = user()
    monkeypatch.setattr(users, "get_user_by_id", lambda *_args: item)

    assert users.get_user(str(item.id), str(item.id), None) is item
    with pytest.raises(HTTPException) as forbidden:
        users.get_user("other", str(item.id), None)
    assert forbidden.value.status_code == 403
    monkeypatch.setattr(users, "get_user_by_id", lambda *_args: None)
    with pytest.raises(HTTPException) as missing:
        users.get_user(str(item.id), str(item.id), None)
    assert missing.value.status_code == 404

    monkeypatch.setattr(users, "update_user", lambda *_args: item)
    assert users.update_user_profile(str(item.id), UserUpdate(full_name="New"), str(item.id), None) is item
    with pytest.raises(HTTPException) as update_forbidden:
        users.update_user_profile("other", UserUpdate(), str(item.id), None)
    assert update_forbidden.value.status_code == 403
    monkeypatch.setattr(users, "update_user", lambda *_args: None)
    with pytest.raises(HTTPException) as update_missing:
        users.update_user_profile(str(item.id), UserUpdate(), str(item.id), None)
    assert update_missing.value.status_code == 404


def test_transaction_routes(monkeypatch):
    cat = category()
    tx = tx_response(cat)
    monkeypatch.setattr(transactions, "get_category_by_id", lambda *_args: cat)
    monkeypatch.setattr(transactions, "create_transaction", lambda *_args: tx)
    monkeypatch.setattr(transactions, "get_user_by_id", lambda *_args: user())
    monkeypatch.setattr(transactions, "calculate_user_balance", lambda *_args, **_kwargs: balance())
    response = transactions.create_new_transaction(create_tx(cat.id), "user", None)
    assert response.transaction.id == tx.id

    monkeypatch.setattr(transactions, "get_category_by_id", lambda *_args: None)
    with pytest.raises(HTTPException) as missing_cat:
        transactions.create_new_transaction(create_tx(cat.id), "user", None)
    assert missing_cat.value.status_code == 400

    monkeypatch.setattr(transactions, "get_user_transactions", lambda *_args: [tx])
    assert transactions.list_transactions(0, 5, "expense", cat.id, "2026-05-01", "2026-05-22", "user", None) == [tx]
    monkeypatch.setattr(transactions, "get_transaction_by_id", lambda *_args: tx)
    assert transactions.get_transaction("tx", "user", None) is tx
    monkeypatch.setattr(transactions, "get_transaction_by_id", lambda *_args: None)
    with pytest.raises(HTTPException) as missing_tx:
        transactions.get_transaction("tx", "user", None)
    assert missing_tx.value.status_code == 404

    monkeypatch.setattr(transactions, "get_category_by_id", lambda *_args: cat)
    monkeypatch.setattr(transactions, "update_transaction", lambda *_args: tx)
    assert transactions.update_existing_transaction("tx", TransactionUpdate(category_id=cat.id), "user", None) is tx
    monkeypatch.setattr(transactions, "get_category_by_id", lambda *_args: None)
    with pytest.raises(HTTPException) as update_cat:
        transactions.update_existing_transaction("tx", TransactionUpdate(category_id=cat.id), "user", None)
    assert update_cat.value.status_code == 400
    monkeypatch.setattr(transactions, "update_transaction", lambda *_args: None)
    with pytest.raises(HTTPException) as update_tx:
        transactions.update_existing_transaction("tx", TransactionUpdate(), "user", None)
    assert update_tx.value.status_code == 404

    monkeypatch.setattr(transactions, "delete_transaction", lambda *_args: True)
    monkeypatch.setattr(transactions, "get_user_by_id", lambda *_args: None)
    monkeypatch.setattr(transactions, "calculate_user_balance", lambda *_args, **_kwargs: balance())
    assert transactions.delete_existing_transaction("tx", "user", None).balance == balance()
    monkeypatch.setattr(transactions, "delete_transaction", lambda *_args: False)
    with pytest.raises(HTTPException) as delete_tx:
        transactions.delete_existing_transaction("tx", "user", None)
    assert delete_tx.value.status_code == 404


def test_bulk_transactions(monkeypatch):
    made = []
    cat = category()
    resolve_category = transactions._resolve_or_create_category
    monkeypatch.setattr(transactions, "_resolve_or_create_category", lambda *_args: cat.id)
    monkeypatch.setattr(transactions, "create_transaction", lambda _db, _user, tx: made.append(tx))
    monkeypatch.setattr(transactions, "get_user_by_id", lambda *_args: user())
    monkeypatch.setattr(transactions, "calculate_user_balance", lambda *_args, **_kwargs: balance())
    payload = transactions.BulkTransactionCreate(
        transactions=[
            transactions.BulkTransactionItem(amount=-4, category="Food", date="invalid"),
            transactions.BulkTransactionItem(amount=6, category="Salary", transaction_type="income"),
        ]
    )

    response = transactions.create_bulk_transactions(payload, "user", None)

    assert response.created_count == 2
    assert made[0].transaction_type == TransactionType.EXPENSE
    monkeypatch.setattr(transactions, "_resolve_or_create_category", resolve_category)
    existing = category()
    monkeypatch.setattr(transactions, "get_category_by_title", lambda *_args: existing)
    assert transactions._resolve_or_create_category(None, "Food") == existing.id
    monkeypatch.setattr(transactions, "get_category_by_title", lambda *_args: None)
    monkeypatch.setattr(transactions, "create_category", lambda *_args: cat)
    assert transactions._resolve_or_create_category(None, "New") == cat.id


@pytest.mark.anyio
async def test_file_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(files.settings, "UPLOADS_DIR", str(tmp_path))
    bad = UploadFile(BytesIO(b"text"), filename="bad.txt", headers={"content-type": "text/plain"})
    with pytest.raises(HTTPException) as unsupported:
        await files.upload_file(bad, "user")
    assert unsupported.value.status_code == 415

    monkeypatch.setattr(files, "MAX_FILE_SIZE", 1)
    large = UploadFile(BytesIO(b"pdf"), filename="big.pdf", headers={"content-type": "application/pdf"})
    with pytest.raises(HTTPException) as too_big:
        await files.upload_file(large, "user")
    assert too_big.value.status_code == 413

    monkeypatch.setattr(files, "MAX_FILE_SIZE", 10)
    good = UploadFile(BytesIO(b"ok"), filename=None, headers={"content-type": "image/png"})
    response = await files.upload_file(good, "user")
    assert response.filename == "upload"
    assert (tmp_path / response.file_id / "upload").read_bytes() == b"ok"
