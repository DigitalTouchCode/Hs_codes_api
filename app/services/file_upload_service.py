import csv
import io
from dataclasses import dataclass

from app.models import HsCode, HsCodeFile

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

    incoming_codes = [obj.hs_code for obj in objects]
    existing_count = HsCode.objects.filter(hs_code__in=incoming_codes).count()

    HsCode.objects.bulk_create(objects, ignore_conflicts=True)

    created = len(objects) - existing_count

    return UploadResult(
        created=created,
        skipped_duplicates=existing_count,
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

        if not {"HS CODE", "GOODS DESCRIPTION"}.issubset(reader.fieldnames or []):
            raise ValueError(
                f"CSV must contain 'HS CODE' and 'GOODS DESCRIPTION' columns. "
                f"Found: {reader.fieldnames}"
            )

        rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc

    if not rows:
        raise ValueError("CSV file contains no data rows.")

    return rows


def _build_objects(rows, hs_code_file):
    objects = []
    skipped_blank = 0

    for row in rows:
        hs_code = row.get("HS CODE", "").strip()
        description = row.get("GOODS DESCRIPTION", "").strip()

        if not hs_code or not description:
            skipped_blank += 1
            continue

        objects.append(
            HsCode(
                hs_code=hs_code,
                description=description,
                hs_code_file=hs_code_file,
            )
        )

    return objects, skipped_blank
