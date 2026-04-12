from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd


@dataclass(frozen=True)
class ValidationIssue:
    message: str


class DataValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        issues_list = list(issues)
        messages = "\n".join(f"- {issue.message}" for issue in issues_list)
        super().__init__(f"Data validation failed:\n{messages}")
        self.issues = issues_list


REQUIRED_PRODUCTS_COLUMNS = {"category", "price"}
TOKEN_COLUMN_OPTIONS = {"ingredient_tokens_clean", "ingredient_tokens", "ingredients"}


def _assert_columns(
    df: pd.DataFrame, required: set[str], label: str, issues: List[ValidationIssue]
) -> None:
    missing = required - set(df.columns)
    if missing:
        issues.append(ValidationIssue(f"{label} missing columns: {sorted(missing)}"))


def _assert_non_empty(
    df: pd.DataFrame, label: str, issues: List[ValidationIssue]
) -> None:
    if df.empty:
        issues.append(ValidationIssue(f"{label} has no rows"))


def _assert_non_empty_strings(
    series: pd.Series, label: str, issues: List[ValidationIssue]
) -> None:
    if series.isna().all():
        issues.append(ValidationIssue(f"{label} is entirely empty"))
        return
    if series.fillna("").str.strip().eq("").mean() > 0.5:
        issues.append(ValidationIssue(f"{label} has >50% empty strings"))


def _assert_prices(series: pd.Series, issues: List[ValidationIssue]) -> None:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().all():
        issues.append(ValidationIssue("price column is non-numeric"))
    elif (numeric < 0).any():
        issues.append(ValidationIssue("price column contains negative values"))


def validate_artifact_inputs(root: Path) -> None:
    data_products = root / "data" / "processed" / "products_with_signals.csv"
    groups_path = root / "features" / "ingredient_groups.json"

    issues: List[ValidationIssue] = []

    if not data_products.exists():
        issues.append(ValidationIssue(f"Missing file: {data_products}"))
    if not groups_path.exists():
        issues.append(ValidationIssue(f"Missing file: {groups_path}"))

    if issues:
        raise DataValidationError(issues)

    products = pd.read_csv(data_products, dtype={"product_id": str})

    _assert_columns(
        products,
        REQUIRED_PRODUCTS_COLUMNS,
        "products_with_signals.csv",
        issues,
    )
    _assert_non_empty(products, "products_with_signals.csv", issues)

    token_columns_present = TOKEN_COLUMN_OPTIONS.intersection(set(products.columns))
    if not token_columns_present:
        issues.append(
            ValidationIssue(
                "products_with_signals.csv missing token text column; expected one of "
                f"{sorted(TOKEN_COLUMN_OPTIONS)}"
            )
        )

    if "price" in products.columns:
        _assert_prices(products["price"], issues)
    if "category" in products.columns:
        _assert_non_empty_strings(products["category"], "category", issues)
    if "ingredient_tokens_clean" in products.columns:
        _assert_non_empty_strings(
            products["ingredient_tokens_clean"],
            "products_with_signals.ingredient_tokens_clean",
            issues,
        )
    elif "ingredient_tokens" in products.columns:
        _assert_non_empty_strings(
            products["ingredient_tokens"],
            "products_with_signals.ingredient_tokens",
            issues,
        )
    elif "ingredients" in products.columns:
        _assert_non_empty_strings(
            products["ingredients"],
            "products_with_signals.ingredients",
            issues,
        )

    if issues:
        raise DataValidationError(issues)
