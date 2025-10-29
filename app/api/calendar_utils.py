import os
from datetime import timezone, timedelta, datetime as dt
from dateutil import parser
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_calendar_service():
    """Return an authenticated google-api-python-client Calendar service."""
    creds = Credentials(
        token=None,  # access token will be refreshed automatically
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"), # can be taken from oauth later
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"), # taken from oauth later
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"), # taken from oauth later
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def get_upcoming_events(home_keywords= []):
    """Return True if the primary calendar shows a busy event *right now*."""
    service = get_calendar_service()
    now = dt.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(hours= 6)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    upcoming_events = []
    for event in events:
        location = (event.get("location") or "").lower()
        summary = (event.get("summary") or "").lower()
        description = (event.get("description") or "").lower()

        at_home = any(kw.lower() in location or kw in summary for kw in home_keywords)

        has_video_link = False
        if "hangoutsMeet" in event:
            has_video_link = True
        if "conferenceData" in event and event["conferenceData"].get("entryPoints"):
            has_video_link = True
        if "zoom.us" in description or "meet.google.com" in description:
            has_video_link = True

        if at_home or has_video_link:
            # send_notification('Confirm At Home', f'Will you be at home during this event - {summary}?')
            continue # Busy but you're at home

       #  send_notification('Confirm Away Mode', f'Will you be away from home for this event - {summary}?')
        upcoming_events.append({'event': event,
                                'start_time': parser.isoparse(event.get("start")['dateTime']).astimezone(tz=timezone.utc).replace(tzinfo=None),
                                'end_time': parser.isoparse(event.get("end")['dateTime']).astimezone(tz=timezone.utc).replace(tzinfo=None) })

    return upcoming_events
    # busy_windows = response["calendars"]["primary"].get("busy", [])
    # return bool(busy_windows)  # away if any event blocks the current instant

def user_is_away(service, home_keywords= []):
    """Return True if the primary calendar shows a busy event *right now*."""
    now = dt.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(minutes=1)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    for event in events:
        location = (event.get("location") or "").lower()
        summary = (event.get("summary") or "").lower()
        description = (event.get("description") or "").lower()

        at_home = any(kw.lower() in location or kw in summary for kw in home_keywords)

        has_video_link = False
        if "hangoutsMeet" in event:
            has_video_link = True
        if "conferenceData" in event and event["conferenceData"].get("entryPoints"):
            has_video_link = True
        if "zoom.us" in description or "meet.google.com" in description:
            has_video_link = True

        if at_home or has_video_link:
            # send_notification('Confirm At Home', f'Will you be at home during this event - {summary}?')
            return False, dt.utcnow()  # Busy but you're at home

       #  send_notification('Confirm Away Mode', f'Will you be away from home for this event - {summary}?')
        return True, parser.isoparse(event.get("end")['dateTime']).astimezone(tz=timezone.utc).replace(tzinfo=None) # Busy and not home

    return False, dt.utcnow()  # No events = you're free/home
    # busy_windows = response["calendars"]["primary"].get("busy", [])
    # return bool(busy_windows)  # away if any event blocks the current instant