from __future__ import annotations

import argparse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.integrations.classroom import GoogleClassroomClient
from app.integrations.oauth import GOOGLE_SCOPES


def main() -> None:
    parser = argparse.ArgumentParser(description="Print Google Classroom courses and coursework.")
    parser.add_argument("--token", required=True, help="OAuth access token for a quick smoke test.")
    args = parser.parse_args()

    credentials = Credentials(token=args.token, scopes=GOOGLE_SCOPES)
    service = build("classroom", "v1", credentials=credentials)
    classroom = GoogleClassroomClient(service)

    for course in classroom.list_courses():
        print(f"{course.get('id')}: {course.get('name')}")
        for work in classroom.list_coursework(str(course["id"]))[:5]:
            print(f"  - {work.get('id')}: {work.get('title')}")


if __name__ == "__main__":
    main()
