from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Dict, List

from sqlalchemy.dialects.postgresql import insert

from deployment.api.db.init_db import init_db
from deployment.api.db.session import SessionLocal, engine
from deployment.api.persistence.models import Product


def normalize_category(raw_category: str, product_name: str = "") -> str:
    if not raw_category and not product_name:
        return "treatment"

    lower = raw_category.lower().strip()
    product_lower = product_name.lower().strip()
    combined = f"{lower} {product_lower}"

    if re.search(
        r"\b(spf\s*\d*|sunscreen|sun\s*screen|broad\s*spectrum|uv)\b", combined
    ):
        return "sunscreen"
    if "eye" in lower or "eye" in product_lower:
        return "eye_cream"
    if "mask" in lower or "mask" in product_lower:
        return "face_mask"
    if any(
        keyword in combined
        for keyword in [
            "clean",
            "cleanser",
            "wash",
            "soap",
            "micellar",
            "scrub",
            "exfoliat",
        ]
    ):
        return "cleanser"
    if any(
        keyword in combined
        for keyword in ["moistur", "cream", "lotion", "balm", "hydrat", "ointment"]
    ):
        return "moisturizer"
    return "treatment"


def _default_csv_path() -> Path:
    env_path = os.getenv("PRODUCTS_CSV_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "processed"
        / "products_with_signals.csv"
    )


def _load_rows(csv_path: Path) -> List[Dict]:
    rows: List[Dict] = []

    with open(csv_path, "r", encoding="utf-8") as file_handle:
        reader = csv.DictReader(file_handle)
        for index, row in enumerate(reader, start=1):
            product_name = (row.get("product_name") or "").strip()
            brand = (row.get("brand") or "").strip()

            if brand and product_name.lower().startswith(brand.lower()):
                product_name = product_name[len(brand) :].strip()

            if "," in product_name:
                product_name = product_name.split(",", 1)[0].strip()

            try:
                price = float(row.get("price", 0) or 0)
            except ValueError:
                price = 0.0

            category_raw = (
                f"{row.get('usage_type', '')} {row.get('category', '')}".strip()
            )
            category = normalize_category(category_raw, product_name=product_name)

            ingredients_value = (row.get("ingredients") or "").strip()
            ingredients = [
                ingredient.strip()
                for ingredient in ingredients_value.split(",")
                if ingredient.strip()
            ]

            rows.append(
                {
                    "product_id": index,
                    "product_name": product_name,
                    "brand": brand,
                    "category": category,
                    "price": price,
                    "image_url": (row.get("image_url") or "").strip(),
                    "ingredients": ingredients,
                    "short_description": "",
                }
            )

    return rows


def seed_products(csv_path: Path) -> int:
    init_db()

    if not csv_path.exists():
        raise FileNotFoundError(f"Products CSV not found: {csv_path}")

    rows = _load_rows(csv_path)
    if not rows:
        return 0

    with SessionLocal() as db:
        if engine.dialect.name == "postgresql":
            stmt = insert(Product).values(rows)
            update_columns = {
                "product_name": stmt.excluded.product_name,
                "brand": stmt.excluded.brand,
                "category": stmt.excluded.category,
                "price": stmt.excluded.price,
                "image_url": stmt.excluded.image_url,
                "ingredients": stmt.excluded.ingredients,
                "short_description": stmt.excluded.short_description,
            }
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=[Product.product_id],
                    set_=update_columns,
                )
            )
        else:
            for row in rows:
                db.merge(Product(**row))

        db.commit()

    return len(rows)


def main() -> None:
    csv_path = _default_csv_path()
    count = seed_products(csv_path)
    print(f"Seeded products: {count} from {csv_path}")


if __name__ == "__main__":
    main()
