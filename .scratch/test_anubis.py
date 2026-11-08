import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotaoff import anubis, library


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if not self.responses:
            raise AssertionError("unexpected extra request")
        return self.responses.pop(0)


def challenge_html(challenge):
    payload = json.dumps(json.dumps(challenge))
    return f'<script id="anubis_challenge" type="application/json">{payload}</script>'


session = FakeSession([FakeResponse("{}")])
assert anubis.fetch_text("/index.php", {"title": "X"}, session=session) == "{}"
assert len(session.calls) == 1

challenge = {"rules": {"difficulty": 1}, "challenge": {"randomData": "seed", "id": "id-1"}}
session = FakeSession([
    FakeResponse(challenge_html(challenge)),
    FakeResponse("", 200),
    FakeResponse('{"ok": 1}'),
])
text = anubis.fetch_text("/index.php", {"title": "T", "action": "raw"}, session=session)
assert text == '{"ok": 1}'
assert len(session.calls) == 3
passed_url, passed_params = session.calls[1]
assert passed_url.endswith("/.within.website/x/cmd/anubis/api/pass-challenge")
assert passed_params["id"] == "id-1"
assert passed_params["redir"] == "/index.php?title=T&action=raw"
assert passed_params["response"].startswith("0")
assert isinstance(passed_params["nonce"], int)

original = anubis.fetch
anubis.fetch = lambda *args, **kwargs: FakeResponse('{"songs": {"1": {}}}')
try:
    payload = library.fetch_remote(timeout=1)
finally:
    anubis.fetch = original
assert payload == {"songs": {"1": {}}}

print("OK")