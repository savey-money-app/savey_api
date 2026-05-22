from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from models.transaction import TransactionType
from schemas.category import CategoryCreate, CategoryUpdate
from schemas.message import MessageCreate
from schemas.transaction import TransactionCreate, TransactionFilter, TransactionUpdate
from schemas.user import UserCreate, UserUpdate
from services import category_service, message_service, transaction_service, user_service


class Query:
    def __init__(self, result=None, scalar=None):
        self.result = result
        self.scalar_result = scalar
        self.calls = []

    def filter(self, *conditions):
        self.calls.append(("filter", conditions))
        return self

    def order_by(self, *columns):
        self.calls.append(("order_by", columns))
        return self

    def offset(self, value):
        self.calls.append(("offset", value))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def all(self):
        return self.result

    def first(self):
        return self.result

    def scalar(self):
        return self.scalar_result


class DB:
    def __init__(self, *queries, fail_commit=False):
        self.queries = list(queries)
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []
        self.fail_commit = fail_commit

    def query(self, *_args):
        return self.queries.pop(0)

    def add(self, value):
        self.added.append(value)

    def delete(self, value):
        self.deleted.append(value)

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, value):
        self.refreshed.append(value)


def transaction_create(category_id):
    return TransactionCreate(
        amount=Decimal("12.50"),
        category_id=category_id,
        transaction_type=TransactionType.EXPENSE,
        description="Lunch",
        date=date(2026, 5, 22),
    )


def test_category_service_crud(monkeypatch):
    category = SimpleNamespace(title="Food")
    create_db = DB()

    created = category_service.create_category(create_db, CategoryCreate(title="Food"))

    assert created.title == "Food"
    assert create_db.added == [created]
    assert category_service.get_all_categories(DB(Query([category]))) == [category]
    assert category_service.get_category_by_id(DB(Query(category)), "category") is category
    assert category_service.get_category_by_title(DB(Query(category)), "Food") is category

    monkeypatch.setattr(category_service, "get_category_by_id", lambda _db, _id: category)
    updated = category_service.update_category(DB(), "category", CategoryUpdate(title="Travel"))
    assert updated.title == "Travel"
    monkeypatch.setattr(category_service, "get_category_by_id", lambda _db, _id: None)
    assert category_service.update_category(DB(), "missing", CategoryUpdate(title="Nope")) is None

    monkeypatch.setattr(category_service, "get_category_by_id", lambda _db, _id: category)
    delete_db = DB()
    assert category_service.delete_category(delete_db, "category")
    assert delete_db.deleted == [category]
    monkeypatch.setattr(category_service, "get_category_by_id", lambda _db, _id: None)
    assert not category_service.delete_category(DB(), "missing")


def test_transaction_service_crud_and_filters(monkeypatch):
    category_id = uuid4()
    data = transaction_create(category_id)
    create_db = DB()

    created = transaction_service.create_transaction(create_db, str(uuid4()), data)

    assert created.amount == data.amount
    assert created.statement_id is None
    tx = SimpleNamespace(description="old")
    assert transaction_service.get_transaction_by_id(DB(Query(tx)), "tx", "user") is tx

    filters = TransactionFilter(
        transaction_type=TransactionType.EXPENSE,
        category_id=category_id,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        min_amount=Decimal("1"),
        max_amount=Decimal("99"),
    )
    rows = [SimpleNamespace(id="tx")]
    assert transaction_service.get_user_transactions(DB(Query(rows)), "user", filters, 3, 4) == rows

    monkeypatch.setattr(transaction_service, "get_transaction_by_id", lambda *_args: tx)
    updated = transaction_service.update_transaction(
        DB(), "tx", "user", TransactionUpdate(description="new")
    )
    assert updated.description == "new"
    monkeypatch.setattr(transaction_service, "get_transaction_by_id", lambda *_args: None)
    assert transaction_service.update_transaction(DB(), "missing", "user", TransactionUpdate()) is None

    monkeypatch.setattr(transaction_service, "get_transaction_by_id", lambda *_args: tx)
    delete_db = DB()
    assert transaction_service.delete_transaction(delete_db, "tx", "user")
    assert delete_db.deleted == [tx]
    monkeypatch.setattr(transaction_service, "get_transaction_by_id", lambda *_args: None)
    assert not transaction_service.delete_transaction(DB(), "missing", "user")


def test_transaction_service_deletes_latest_transaction_and_statement_batch():
    last_transaction = SimpleNamespace(id="latest")
    delete_latest_db = DB(Query(last_transaction))

    assert transaction_service.delete_latest_transaction(delete_latest_db, "user")
    assert delete_latest_db.deleted == [last_transaction]
    assert not transaction_service.delete_latest_transaction(DB(Query(None)), "user")

    latest_statement_transaction = SimpleNamespace(statement_id=uuid4())
    statement_transactions = [SimpleNamespace(id="one"), SimpleNamespace(id="two")]
    delete_statement_db = DB(Query(latest_statement_transaction), Query(statement_transactions))

    assert transaction_service.delete_latest_statement_transactions(delete_statement_db, "user") == 2
    assert delete_statement_db.deleted == statement_transactions
    assert transaction_service.delete_latest_statement_transactions(DB(Query(None)), "user") == 0


def test_transaction_balance_uses_income_expense_and_limits():
    db = DB(Query(scalar=150), Query(scalar=40), Query(scalar=30), Query(scalar=10))

    balance = transaction_service.calculate_user_balance(db, "user", 100, 25)

    assert balance.balance == 110
    assert balance.monthly_spending == 30
    assert balance.monthly_limit == 100
    assert balance.daily_spending == 10
    assert balance.daily_limit == 25


def test_user_service_crud(monkeypatch):
    data = UserCreate(
        email="person@example.com",
        password="secret",
        full_name="Person",
        currency="kzt",
        preferred_language="en",
    )
    monkeypatch.setattr(user_service, "hash_password", lambda _password: "hash")
    created = user_service.create_user(DB(), data)

    assert created.password_hash == "hash"
    assert created.currency == "KZT"
    assert user_service.get_user_by_id(DB(Query(created)), "user") is created
    assert user_service.get_user_by_email(DB(Query(created)), data.email) is created

    with pytest.raises(HTTPException, match="Email already"):
        user_service.create_user(DB(fail_commit=True), data)

    profile = user_service.create_user_profile(DB(), "better-auth-id")
    assert profile.email == "better-auth-id@better-auth.local"
    monkeypatch.setattr(user_service, "get_user_by_id", lambda *_args: profile)
    assert user_service.update_user(DB(), "user", UserUpdate(full_name="New")).full_name == "New"
    monkeypatch.setattr(user_service, "get_user_by_id", lambda *_args: None)
    assert user_service.update_user(DB(), "missing", UserUpdate()) is None


def test_message_service_crud():
    user_id = uuid4()
    created_at = date(2026, 5, 22)
    message = message_service.create_message(
        DB(),
        MessageCreate(
            user_id=user_id,
            content="hello",
            is_user=True,
            had_attachment=False,
            created_at=created_at,
        ),
    )
    newest, oldest = SimpleNamespace(id="new"), SimpleNamespace(id="old")

    assert message.content == "hello"
    assert message_service.get_user_messages(DB(Query([newest, oldest])), "user") == [oldest, newest]
    assert message_service.get_message_by_id(DB(Query(message)), "message", "user") is message
