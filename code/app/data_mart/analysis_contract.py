import pandas as pd
OBSERVATION_END = pd.Timestamp("2026-02-28 00:00:00", tz="UTC")
GROWTH_STATUSES = ("Complete", "Shipped", "Processing", "Returned")
PURCHASE_STATUS = "Complete"
DEFAULT_PERIOD_YEARS = 3


def default_period(years=DEFAULT_PERIOD_YEARS):
    """대시보드 기본 진단 기간: 관측 종료 전 열두 달이 다 찬 마지막 연도까지 years개 연도 (start_year, end_year)."""
    end_year = OBSERVATION_END.year - 1
    return end_year - years + 1, end_year

CATEGORY_GROUP_MAP = {'Underwear': 'Consumable', 'Socks & Hosiery': 'Consumable', 'Tops & Tees': 'Consumable', 'Swim': 'Consumable', 'Sleep & Lounge': 'Consumable', 'Leggings': 'Consumable', 'Socks': 'Consumable', 'Intimates': 'Consumable', 'Outerwear & Coats': 'Non-Consumable', 'Suits & Sport Coats': 'Non-Consumable', 'Blazers & Jackets': 'Non-Consumable', 'Fashion Hoodies & Sweatshirts': 'Non-Consumable', 'Sweaters': 'Non-Consumable', 'Suits': 'Non-Consumable', 'Dresses': 'Non-Consumable', 'Jumpsuits & Rompers': 'Non-Consumable', 'Plus': 'Non-Consumable', 'Pants': 'Neutral', 'Pants & Capris': 'Neutral', 'Jeans': 'Neutral', 'Shorts': 'Neutral', 'Skirts': 'Neutral', 'Clothing Sets': 'Neutral', 'Accessories': 'Neutral', 'Maternity': 'Neutral', 'Active': 'Neutral'}
