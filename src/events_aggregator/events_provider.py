from urllib.parse import parse_qs, urlparse

import httpx


class EventsProviderClient:
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url
        self.api_token = api_token

    def get_events(self, changed_at: str, cursor: str | None = None):
        params = {"changed_at": changed_at}
        if cursor is not None:
            params["cursor"] = cursor
        response = httpx.get(
            self.api_url + "/api/events/",
            headers={"x-api-key": self.api_token},
            params=params,
        )
        response.raise_for_status()
        return response.json()


class EventsPaginator:
    def __init__(self, client: EventsProviderClient, changed_at: str):
        self.client = client
        self.changed_at = changed_at

        self.current_page = []
        self.current_index = 0

        self.next_cursor = None

        self.started = False
        self.finished = False

    @staticmethod
    def _extract_cursor(next_page_url: str):
        parsed_next_page_url = urlparse(url=next_page_url)
        params = parse_qs(qs=parsed_next_page_url.query)
        return params["cursor"][0]

    def _load_page(self):
        event_response = self.client.get_events(changed_at=self.changed_at, cursor=self.next_cursor)
        self.current_page = event_response["results"]
        if event_response["next"] is not None:
            self.next_cursor = self._extract_cursor(event_response["next"])
        else:
            self.next_cursor = None
        self.current_index = 0

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            if self.finished:
                raise StopIteration

            if not self.started:
                self._load_page()
                self.started = True

            if self.current_index < len(self.current_page):
                current_event = self.current_page[self.current_index]
                self.current_index += 1
                return current_event

            if self.next_cursor is not None:
                self._load_page()
            else:
                self.finished = True
