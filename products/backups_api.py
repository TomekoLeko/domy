"""
Endpointy diagnostyczne (tylko lokalnie, tylko superuser).

api_sync_dev_images: lustrzana synchronizacja plikow graficznych na S3 z folderu
produkcyjnego `product_images/` do deweloperskiego `development_images/`, zeby po
zaciagnieciu bazy z produkcji zdjecia wyswietlaly sie lokalnie.

Kopiowanie odbywa sie po stronie S3 (CopyObject, ten sam bucket) — nic nie laduje
sie na serwer aplikacji.
"""

import boto3
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

SOURCE_PREFIX = "product_images/"
DEST_PREFIX = "development_images/"


def _s3_client():
    return boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )


def _list_objects(client, bucket, prefix):
    """Zwraca mape {klucz_wzgledny: rozmiar} dla obiektow pod prefiksem."""
    result = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key == prefix:  # sam "folder"
                continue
            relative = key[len(prefix):]
            if not relative:
                continue
            result[relative] = obj["Size"]
    return result


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_sync_dev_images(request):
    # Tylko lokalnie — nigdy na produkcji (kod jest w tym samym repo co prod).
    if getattr(settings, "ENVIRONMENT", "development") == "production":
        return Response(
            {"detail": "Operacja niedostepna na produkcji."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Tylko superuser (UI to ukrywa, ale autoryzacje egzekwuje backend).
    if not request.user.is_superuser:
        return Response(
            {"detail": "Brak uprawnien (wymagany superuser)."},
            status=status.HTTP_403_FORBIDDEN,
        )

    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    if not bucket:
        return Response(
            {"detail": "Brak konfiguracji AWS_STORAGE_BUCKET_NAME."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        client = _s3_client()
        source = _list_objects(client, bucket, SOURCE_PREFIX)

        # Zabezpieczenie: pusty folder zrodlowy = najpewniej blad konfiguracji,
        # nie kasujemy wtedy niczego w folderze docelowym.
        if not source:
            return Response(
                {
                    "detail": (
                        "Folder zrodlowy '%s' jest pusty — przerwano, zeby nie "
                        "wyczyscic folderu docelowego." % SOURCE_PREFIX
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        dest = _list_objects(client, bucket, DEST_PREFIX)

        copied = 0
        for relative, size in source.items():
            if dest.get(relative) == size:
                continue  # identyczny plik juz jest — pomijamy
            client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": SOURCE_PREFIX + relative},
                Key=DEST_PREFIX + relative,
            )
            copied += 1

        # Mirror: usuwamy z docelowego to, czego nie ma w zrodle (jak `aws s3 sync --delete`).
        stale = [rel for rel in dest if rel not in source]
        deleted = 0
        for batch_start in range(0, len(stale), 1000):
            batch = stale[batch_start:batch_start + 1000]
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": DEST_PREFIX + rel} for rel in batch]},
            )
            deleted += len(batch)

        return Response(
            {
                "detail": "Zsynchronizowano zdjecia.",
                "source": SOURCE_PREFIX,
                "destination": DEST_PREFIX,
                "source_count": len(source),
                "copied": copied,
                "deleted": deleted,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:  # noqa: BLE001 — zwracamy czytelny blad do UI
        return Response(
            {"detail": "Blad synchronizacji zdjec: %s" % exc},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
