import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


DRIVE_FILES = {
    "sleeper_snapshot.json": (
        "1b4RTi5PuFi9ULGK-khALY_niPyS2Ji4U",
        "application/json",
    ),
    "sleeper_daily.json": (
        "15h_0HS2APJEyHMrUWRgN3UympUDKmWik",
        "application/json",
    ),
    "index.html": (
        "1vSuIm0I8GwXT6SwNJZ4o6XVQqfJcj3Si",
        "text/html",
    ),
    "yahoo_snapshot.json": (
        "15encsc7sDAqWIXfB43d8PqE-4MEpgxNz",
        "application/json",
    ),
    "yahoo_daily.json": (
        "1QMOOV5axM-CTSHgtWSsPq6wd4jjjGS18",
        "application/json",
    ),
    "yahoo_status.json": (
        "1--xCzrGpAnFUgOVlSvXBn0qB8SFifovf",
        "application/json",
    ),
}


requested_files = os.environ.get("DRIVE_UPLOAD_FILES", "").strip()
if requested_files:
    upload_files = [name.strip() for name in requested_files.split(",") if name.strip()]
    unknown_files = sorted(set(upload_files) - set(DRIVE_FILES))
    if unknown_files:
        raise ValueError(f"Unknown Drive upload files: {', '.join(unknown_files)}")
else:
    upload_files = list(DRIVE_FILES)

credentials_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=["https://www.googleapis.com/auth/drive"],
)

drive = build(
    "drive",
    "v3",
    credentials=credentials,
    cache_discovery=False,
)

for local_file in upload_files:
    drive_file_id, mime_type = DRIVE_FILES[local_file]
    media = MediaFileUpload(
        local_file,
        mimetype=mime_type,
        resumable=False,
    )

    result = (
        drive.files()
        .update(
            fileId=drive_file_id,
            media_body=media,
            fields="id,name,modifiedTime",
        )
        .execute()
    )

    print(
        f"Updated {local_file}: "
        f"{result['id']} at {result['modifiedTime']}"
    )
