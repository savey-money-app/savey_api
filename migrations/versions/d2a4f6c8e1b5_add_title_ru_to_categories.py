"""Add title_ru to categories

Revision ID: d2a4f6c8e1b5
Revises: c7e9a4b2f8d3
Create Date: 2026-02-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'd2a4f6c8e1b5'
down_revision: Union[str, None] = 'c7e9a4b2f8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mapping of English titles to Russian translations
TRANSLATIONS = {
    "Food & Dining": "Еда и рестораны",
    "Groceries": "Продукты",
    "Transportation": "Транспорт",
    "Fuel": "Топливо",
    "Education": "Образование",
    "Clothing": "Одежда",
    "Entertainment": "Развлечения",
    "Healthcare": "Здоровье",
    "Housing & Rent": "Жильё и аренда",
    "Utilities": "Коммунальные услуги",
    "Shopping": "Покупки",
    "Personal Care": "Личный уход",
    "Travel": "Путешествия",
    "Subscriptions": "Подписки",
    "Insurance": "Страхование",
    "Gifts & Donations": "Подарки и пожертвования",
    "Other Expense": "Прочие расходы",
    "Salary": "Зарплата",
    "Freelance": "Фриланс",
    "Passive Income": "Пассивный доход",
    "Investments": "Инвестиции",
    "Business Income": "Доход от бизнеса",
    "Gifts Received": "Полученные подарки",
    "Refunds": "Возвраты",
    "Bonus": "Бонус",
    "Other Income": "Прочие доходы",
}


def upgrade() -> None:
    # Add title_ru column
    op.add_column('categories', sa.Column('title_ru', sa.String(), nullable=True))

    # Populate Russian translations for seeded categories
    conn = op.get_bind()
    for title_en, title_ru in TRANSLATIONS.items():
        conn.execute(
            text("UPDATE categories SET title_ru = :title_ru WHERE title = :title"),
            {"title_ru": title_ru, "title": title_en}
        )


def downgrade() -> None:
    op.drop_column('categories', 'title_ru')
