# --- Стандартные библиотеки ---
import random

def generate_test_gifts(count=1):
    """Генерирует список тестовых (фейковых) подарков для использования в тестах и разработке."""
    gifts = []
    for i in range(count):
        gift = {
            "id": f"0000{i}",
            "price": 5000 + 1000 * random.choice([i, i, i, i, i, i, i, i, i, i + 1]),
            "supply": 9000 + 1000 * i,
            "left": 4000 + 1000 * i,
            "sticker_file_id": f"FAKE_FILE_ID_{i}",
            "emoji": "🎁"
        }
        gifts.append(gift)

    return gifts