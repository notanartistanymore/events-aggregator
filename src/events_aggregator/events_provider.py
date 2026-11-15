from collections.abc import Iterator
from datetime import date
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx


class EventsProviderClient:
    def __init__(self, api_url: str, api_token: str, timeout: float = 20.0):
        self.api_url = api_url.rstrip("/")
        self.headers = {"x-api-key": api_token}
        self.timeout = timeout

    def _request(self, method: str, path: str, *, params=None, json=None) -> dict:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.request(
                method,
                self.api_url + path,
                headers=self.headers,
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()

    def get_events(self, changed_at: str, cursor: str | None = None) -> dict:
        params = {"changed_at": changed_at}
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", "/api/events/", params=params)

    def get_seats(self, event_id: UUID) -> dict:
        return self._request("GET", f"/api/events/{event_id}/seats/")

    def register(
        self, event_id: UUID, first_name: str, last_name: str, email: str, seat: str
    ) -> dict:
        return self._request(
            "POST",
            f"/api/events/{event_id}/register/",
            json={"first_name": first_name, "last_name": last_name, "email": email, "seat": seat},
        )

    def unregister(self, event_id: UUID, ticket_id: UUID) -> dict:
        return self._request(
            "DELETE", f"/api/events/{event_id}/unregister/", json={"ticket_id": str(ticket_id)}
        )


class EventsPaginator(Iterator[dict]):
    def __init__(self, client: EventsProviderClient, changed_at: str | date = "2000-01-01"):
        self.client = client
        self.changed_at = str(changed_at)
        self.current_page: list[dict] = []
        self.current_index = 0
        self.next_cursor: str | None = None
        self.started = False
        self.finished = False
        self.seen_cursors: set[str] = set()

    def _load_page(self) -> None:
        response = self.client.get_events(self.changed_at, cursor=self.next_cursor)
        self.current_page = response["results"]
        self.current_index = 0
        url = response.get("next")
        if url is None:
            self.next_cursor = None
        else:
            values = parse_qs(urlparse(url).query).get("cursor")
            if not values:
                raise ValueError("Provider next URL missing cursor")
            cursor = values[0]
            if cursor in self.seen_cursors:
                raise ValueError("Provider repeated cursor")
            self.seen_cursors.add(cursor)
            self.next_cursor = cursor
        self.started = True

    def __iter__(self) -> "EventsPaginator":
        return self

    def __next__(self) -> dict:
        while not self.finished:
            if not self.started:
                self._load_page()
            if self.current_index < len(self.current_page):
                event = self.current_page[self.current_index]
                self.current_index += 1
                return event
            if self.next_cursor is None:
                self.finished = True
                break
            self._load_page()
        raise StopIteration
