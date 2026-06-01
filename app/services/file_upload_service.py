import csv
import io
from dataclasses import dataclass

from .models import HsCode, HsCodeFile, Category
from category_service import HS_CHAPTER_CATEGORIES, get_or_create_category_for_hs_code


@dataclass
class UploadResult:
    created: int
    skipped_duplicates: int
    skipped_blank_rows: int
    total_rows: int
    hs_code_file_id: int


def process_hs_code_csv(uploaded_file) -> UploadResult:
    text = _decode_file(uploaded_file)
    rows = _parse_csv(text)

    hs_code_file = HsCodeFile.objects.create(hs_code_file=uploaded_file)
    objects, skipped_blank = _build_objects(rows, hs_code_file)

    created_objects = HsCode.objects.bulk_create(objects, ignore_conflicts=True)

    return UploadResult(
        created=len(created_objects),
        skipped_duplicates=len(objects) - len(created_objects),
        skipped_blank_rows=skipped_blank,
        total_rows=len(rows),
        hs_code_file_id=hs_code_file.pk,
    )


# helpers
def _decode_file(uploaded_file) -> str:
    try:
        return uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File encoding error: {exc}") from exc


def _parse_csv(text: str) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(text))

        if not {"hs_code", "description"}.issubset(reader.fieldnames or []):
            raise ValueError(
                f"CSV must contain 'hs_code' and 'description' columns. "
                f"Found: {reader.fieldnames}"
            )

        rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc

    if not rows:
        raise ValueError("CSV file contains no data rows.")

    return rows


def _build_objects(rows, hs_code_file):
    from .models import Category

    objects = []
    skipped_blank = 0
    category_cache: dict[str, Category] = {}

    for row in rows:
        hs_code = row.get("hs_code", "").strip()
        description = row.get("description", "").strip()

        if not hs_code or not description:
            skipped_blank += 1
            continue

        chapter = hs_code[:2]
        if chapter not in category_cache:
            name = HS_CHAPTER_CATEGORIES.get(chapter, f"Chapter {chapter}")
            category, _ = Category.objects.get_or_create(name=name)
            category_cache[chapter] = category

        objects.append(
            HsCode(
                hs_code=hs_code,
                description=description,
                category=category_cache[chapter],
                hs_code_file=hs_code_file,
            )
        )

    return objects, skipped_blank
