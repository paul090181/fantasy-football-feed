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
}


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

for local_file, (drive_file_id, mime_type) in DRIVE_FILES.items():
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
