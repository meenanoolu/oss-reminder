import json, requests

topic = json.load(open("config.json"))["ntfy_topic"]
requests.post(
    f"https://ntfy.sh/{topic}",
    data="Test: if you see this, the reminder works!".encode("utf-8"),
    headers={"Title": "OSS Reminder test", "Tags": "tada"},
)
print("sent")