from fastapi import FastAPI, Query, Body
import httpx
import os
from fastapi.responses import JSONResponse

app = FastAPI()

API_KEY = os.getenv("CRELATE_API_KEY") or "46gcq4k7bw9yysb9thazasxxwy"
BASE_URL = "https://app.crelate.com/api3"

async def fetch_crelate_data(path: str, params: dict = {}):
    url = f"{BASE_URL}/{path}"
    params["api_key"] = API_KEY
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return {
                "requested_url": str(response.url),
                "status_code": response.status_code,
                "error": response.text
            }
        try:
            return response.json()
        except Exception as e:
            return {
                "requested_url": str(response.url),
                "status_code": response.status_code,
                "error": f"Failed to parse JSON: {str(e)}",
                "raw_text": response.text
            }

@app.get("/contacts")
async def get_contacts(
    limit: int = Query(100, ge=1, le=100),
    offset: int = 0,
    full_name: str = None,
    tag: str = None,
    created_by: str = None,
    owner: str = None,
    primary_owner: str = None
):
    """
    Fetch contacts and apply optional filters. Returns full contact records.
    """
    try:
        params = {"limit": limit, "offset": offset}
        raw_data = await fetch_crelate_data("contacts", params)
        if not raw_data or not isinstance(raw_data, dict):
            return {"error": "Unexpected API response format", "response": raw_data}
        contacts = raw_data.get("Data")
        if contacts is None:
            return {"error": "Missing 'Data' key in API response", "response": raw_data}

        def matches_filters(contact):
            if not isinstance(contact, dict):
                return False
            if full_name and contact.get("FullName", "").lower() != full_name.lower():
                return False
            if created_by:
                creator = contact.get("CreatedById") or {}
                if creator.get("Title", "").lower() != created_by.lower():
                    return False
            if owner:
                owners = contact.get("Owners") or []
                if not any(o.get("Title", "").lower() == owner.lower() for o in owners if isinstance(o, dict)):
                    return False
            if primary_owner:
                owners = contact.get("Owners") or []
                primary = next((o for o in owners if o.get("IsPrimary") and isinstance(o, dict)), None)
                if not primary or primary.get("Title", "").lower() != primary_owner.lower():
                    return False
            if tag:
                tags_dict = contact.get("Tags") or {}
                match = False
                for tag_list in tags_dict.values():
                    if isinstance(tag_list, list) and any(t.get("Title", "").lower() == tag.lower() for t in tag_list if isinstance(t, dict)):
                        match = True
                        break
                if not match:
                    return False
            return True

        filtered = [c for c in contacts if matches_filters(c)]
        return {"records": filtered}

    except Exception as e:
        return {"error": "Exception caught in get_contacts", "detail": str(e)}

@app.post("/post_screen_activity")
async def post_screen_activity(payload: dict = Body(...)):
    """
    Post a Screen activity to a specified contact.
    Required fields in payload: EntityId (contact ID), Notes (string)
    """
    try:
        contact_id = payload.get("EntityId")
        notes = payload.get("Notes")
        if not contact_id or not notes:
            return JSONResponse(status_code=400, content={"error": "Missing required EntityId or Notes"})

        activity_payload = {
            "entity": {
                "ParentId": {
                    "Id": contact_id,
                    "EntityName": "Contacts"
                },
                "VerbId": {
                    "Id": "2d4edbf9-a7a2-4174-ae53-a8f900bb0381",
                    "Title": "Screen"
                },
                "Subject": "Screen via API",
                "Html": notes,
                "IsEngagement": True,
                "Completed": True,
                "When": None  # You may add a timestamp here
            }
        }

        url = f"{BASE_URL}/activities"
        headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=activity_payload, headers=headers)
            if response.status_code != 200:
                return {
                    "error": "Failed to post activity",
                    "status_code": response.status_code,
                    "response": response.text
                }
            return {"success": True, "response": response.json()}

    except Exception as e:
        return {"error": "Exception occurred while posting activity", "detail": str(e)}
