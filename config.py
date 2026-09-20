import re

KNOWN_BRANDS = [
    "домик в деревне", "простоквашино", "брест-литовск", "экомилк", "савушкин",
    "вязанка", "ближние горки", "черкизово", "клинский", "дымов",
    "барилла", "шебекинские", "макфа", "мистраль", "националь",
    "микадо", "бондюэль", "фрау марта", "дядя ваня",
    "хайнц", "махеев", "кальве", "слобода",
    "чистая линия", "коровка из кореновки", "магнат", "инмарко",
    "черноголовка", "добрый", "рич", "моя семья", "адреналин",
    "барон", "бахрома", "рузское", "останкино"
]

ITEM_TO_ZONE = {
    "Молоко 3.2%": "Молочный отдел",
    "Молоко 2.5%": "Молочный отдел",
    "Йогурт клубничный": "Молочный отдел",
    "Кефир 2.5%": "Молочный отдел",
    "Хлеб Бородинский": "Хлебный отдел",
    "Багет французский": "Хлебный отдел",
    "Бананы Эквадор": "Овощи и фрукты",
    "Бананы мини": "Овощи и фрукты",
    "Яблоки Гала": "Овощи и фрукты",
    "Куриное филе 1кг": "Свежее мясо",
    "Вода 5л": "Вода и соки",
    "Сыр Российский": "Здоровое питание и сыры"
}

SEED_PRODUCTS = [
    "Молоко 3.2%", "Молоко 2.5%", "Йогурт клубничный", "Кефир 2.5%",
    "Хлеб Бородинский", "Багет французский",
    "Бананы Эквадор", "Бананы мини", "Яблоки Гала",
    "Куриное филе 1кг", "Вода 5л", "Сыр Российский"
]

ZONE_SPEED_MODIFIERS = {
    "Молочный отдел": 40.0,
    "Хлебный отдел": 30.0,
    "Овощи и фрукты": 60.0,
    "Свежее мясо": 75.0,
    "Вода и соки": 35.0,
    "Здоровое питание и сыры": 50.0
}

DEFAULT_PICK_TIME = 45.0

STORES_TOPOLOGIES = {
    "globus": {
        "Вода и соки": 1,
        "Здоровое питание и сыры": 2,
        "Молочный отдел": 3,
        "Свежее мясо": 4,
        "Овощи и фрукты": 5,
        "Хлебный отдел": 6
    },
    "perekrestok_smart": {
        "Овощи и фрукты": 1,
        "Хлебный отдел": 2,
        "Молочный отдел": 3,
        "Здоровое питание и сыры": 4,
        "Свежее мясо": 5,
        "Вода и соки": 6
    },
    "pyaterochka_modern": {
        "Хлебный отдел": 1,
        "Овощи и фрукты": 2,
        "Молочный отдел": 3,
        "Здоровое питание и сыры": 4,
        "Вода и соки": 5,
        "Свежее мясо": 6
    },
    "auchan_mega": {
        "Вода и соки": 1,
        "Здоровое питание и сыры": 2,
        "Молочный отдел": 3,
        "Хлебный отдел": 4,
        "Овощи и фрукты": 5,
        "Свежее мясо": 6
    },
    "magnit_family": {
        "Вода и соки": 1,
        "Свежее мясо": 2,
        "Хлебный отдел": 3,
        "Здоровое питание и сыры": 4,
        "Молочный отдел": 5,
        "Овощи и фрукты": 6
    }
}

STOP_WORDS = {
    "пастеризованное", "нарезной", "свежие", "extra", "премиум",
    "цельное", "классический", "подложка", "фасовка", "лоток", "упаковка"
}

assert set(SEED_PRODUCTS).issubset(set(ITEM_TO_ZONE.keys())), "SEED_PRODUCTS must be a subset of ITEM_TO_ZONE"
for store, topology in STORES_TOPOLOGIES.items():
    assert set(topology.keys()).issubset(
        set(ZONE_SPEED_MODIFIERS.keys())), f"Missing speed modifier for zones in store {store}"


def clean_item_name(raw_name: str) -> str:
    cleaned = raw_name.lower().replace('ё', 'е').replace('%', '').replace(',', '.')
    for brand in KNOWN_BRANDS:
        cleaned = re.sub(rf'(?<![а-яе]){brand}(?![а-яе])', '', cleaned)
    cleaned = re.sub(r'[^\w\s.]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def extract_anchor_noun(cleaned_name: str) -> str:
    tokens = cleaned_name.split()
    valid_tokens = [t for t in tokens if re.match(r'^[а-яе]{4,}$', t) and t not in STOP_WORDS]
    if not valid_tokens:
        return cleaned_name
    return max(valid_tokens, key=len)


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        cur_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = cur_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            cur_row.append(min(insertions, deletions, substitutions))
        prev_row = cur_row
    return prev_row[-1]


def find_zone_for_item(item_name: str) -> str:
    query_cleaned = clean_item_name(item_name)

    for catalog_item, zone in ITEM_TO_ZONE.items():
        if clean_item_name(catalog_item) == query_cleaned:
            return zone

    query_tokens = set(query_cleaned.split()) - STOP_WORDS
    for catalog_item, zone in ITEM_TO_ZONE.items():
        catalog_tokens = set(clean_item_name(catalog_item).split()) - STOP_WORDS
        if query_tokens.issubset(catalog_tokens) and query_tokens:
            return zone

    query_anchor = extract_anchor_noun(query_cleaned)
    if query_anchor:
        best_zone = None
        min_dist = float('inf')
        for catalog_item, zone in ITEM_TO_ZONE.items():
            cat_cleaned = clean_item_name(catalog_item)
            if extract_anchor_noun(cat_cleaned) == query_anchor:
                dist = levenshtein_distance(query_cleaned, cat_cleaned)
                if dist < min_dist and dist <= int(len(cat_cleaned) * 0.4):
                    min_dist = dist
                    best_zone = zone
        if best_zone:
            return best_zone

    return "Без зоны"


def get_zone_step_for_store(store_topology: dict, zone_name: str) -> int:
    return store_topology.get(zone_name, 0)


def extract_weight_kg(item_name: str) -> float:
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(кг|г)', item_name, re.IGNORECASE)
    if not match:
        return 0.0
    value = float(match.group(1).replace(',', '.'))
    unit = match.group(2).lower()
    if unit == 'кг':
        if value == 1.0 and "1кг" in item_name.replace(" ", "").lower():
            return 0.0
        return value
    return value / 1000.0