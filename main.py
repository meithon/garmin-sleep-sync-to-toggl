import json
from base64 import b64encode
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List
import garth
import pytz
import requests
import os
from garth.exc import GarthException


@dataclass
class ProcessedSleepData:
    sleep_start: datetime
    sleep_end: datetime
    is_entryied: bool = False

    def to_dict(self):
        return {
            "sleep_start": self.sleep_start.isoformat(),
            "sleep_end": self.sleep_end.isoformat(),
            "is_entryied": self.is_entryied,
        }

    @staticmethod
    def from_dict(data):
        return ProcessedSleepData(
            sleep_start=datetime.fromisoformat(data["sleep_start"]),
            sleep_end=datetime.fromisoformat(data["sleep_end"]),
            is_entryied=data.get("is_entryied", False),
        )


@dataclass
class SleepData:
    data: List[ProcessedSleepData]

    def to_dict(self):
        return {"data": [item.to_dict() for item in self.data]}

    @staticmethod
    def from_dict(data):
        return SleepData(
            data=[ProcessedSleepData.from_dict(item) for item in data["data"]]
        )


def get_env_variable(var_name: str):
    value = os.getenv(var_name)
    if value is None:
        raise EnvironmentError(f"Environment variable {var_name} not found")
    return value


def save_sleep_data_to_file(sleep_data: SleepData, filename: str):
    with open(filename, "w") as f:
        json.dump(sleep_data.to_dict(), f)


def load_sleep_data_from_file(filename: str) -> SleepData:
    with open(filename, "r") as f:
        data = json.load(f)
        return SleepData.from_dict(data)


def getGarthSleepData(sleep_date: date):
    email = get_env_variable("GARMIN_CONNECT_EMAIL")
    password = get_env_variable("GARMIN_CONNECT_PASSWORD")
    # If there's MFA, you'll be prompted during the login
    garth.resume("~/.garth")
    try:
        garth.client.username
    except GarthException:
        # Session is expired. You'll need to log in aga
        garth.login(email, password)
        garth.save("~/.garth")

    # sleep = garth.connectapi(
    #     f"/wellness-service/wellness/dailySleepData/{garth.client.username}",
    #     params={"date": "2024-08-07", "nonSleepBufferMinutes": 60},
    # )
    sleep = garth.SleepData.get(sleep_date)
    if not sleep:
        raise Exception("no sleep data")

    sleep_start = datetime.fromtimestamp(
        sleep.daily_sleep_dto.sleep_start_timestamp_gmt / 1000
    ).replace(tzinfo=pytz.timezone("Asia/Tokyo"))
    sleep_end = datetime.fromtimestamp(
        sleep.daily_sleep_dto.sleep_end_timestamp_gmt / 1000
    ).replace(tzinfo=pytz.timezone("Asia/Tokyo"))
    #
    return ProcessedSleepData(sleep_start=sleep_start, sleep_end=sleep_end)


def getTogglTimeEntries():
    api_token = get_env_variable("TOGGL_API_TOKEN").encode("ascii")
    data = requests.get(
        "https://api.track.toggl.com/api/v9/me/time_entries/current",
        headers={
            "content-type": "application/json",
            "Authorization": "Basic %s"
            # % b64encode(b"<email>:<password>").decode("ascii"),
            % b64encode(api_token).decode("ascii"),
        },
    )
    # print(data)
    # print(data.json())


def createTogglTimeEntries(sleep_data: ProcessedSleepData):
    workspace_id = 4167965
    sleep_project_id = 203342839
    api_token = get_env_variable("TOGGL_API_TOKEN").encode("ascii")

    data = requests.post(
        f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries",
        json={
            "billable": False,
            "created_with": "service",
            "description": "string",
            # "duration": "integer",
            # "duronly": "boolean",
            # "pid": "integer",
            "project_id": sleep_project_id,
            # "shared_with_user_ids": ["integer"],
            "start": sleep_data.sleep_start.isoformat(),  #  UTC
            # "start_date": "string",
            "stop": sleep_data.sleep_end.isoformat(),  #  UTC(),
            # "tag_action": "string",
            # "tag_ids": ["integer"],
            # "tags": ["string"],
            # "task_id": "integer",
            # "tid": "integer",
            # "uid": "integer",
            # "user_id": "integer",
            # "wid": "integer",
            "workspace_id": workspace_id,
        },
        headers={
            "content-type": "application/json",
            "Authorization": "Basic %s" % b64encode(api_token).decode("ascii"),
        },
    )
    print(data.status_code)
    print(data.json())


start_date = date(2024, 7, 7)
end_date = date(2024, 8, 7)
loaded_sleep_data = load_sleep_data_from_file("sleep_data.json")

for day_offset in range((end_date - start_date).days):
    current_date = start_date + timedelta(days=day_offset)
    print("========================")
    print(current_date.ctime())
    # Check if sleep data already exists for the current date
    existing_data_dates = [
        item.sleep_end.date().ctime() for item in loaded_sleep_data.data
    ]
    print(existing_data_dates)

    if any(item_date == current_date.ctime() for item_date in existing_data_dates):
        print(f"already exists: {current_date}")
        continue

    loaded_sleep_data.data.append(getGarthSleepData(current_date))


not_entryied_sleep_data = list(
    filter(lambda x: x.is_entryied is False, loaded_sleep_data.data)
)

for sleep in not_entryied_sleep_data:
    createTogglTimeEntries(sleep)
    sleep.is_entryied = True

save_sleep_data_to_file(SleepData(data=loaded_sleep_data.data), "sleep_data.json")
