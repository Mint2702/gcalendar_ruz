from aiohttp import ClientSession
from datetime import datetime, timedelta

from . import nvr_api
from ..utils import camel_to_snake
from ..redis_caching.caching import cache
from ..utils import semlock


class RuzApi:
    def __init__(self, url: str = "http://92.242.58.221/ruzservice.svc"):
        self.url = url

    # building id МИЭМа = 92
    @cache
    @semlock("ruz")
    async def get_auditoriumoid(self, building_id: int = 92):
        async with ClientSession() as session:
            res = await session.get(f"{self.url}/auditoriums?buildingoid=0")
            async with res:
                all_auditories = await res.json()

        return [
            room
            for room in all_auditories
            if room["buildingGid"] == building_id and room["typeOfAuditorium"] != "Неаудиторные"
        ]

    @cache
    @semlock("ruz")
    async def get_classes(self, ruz_room_id: str, online: bool = False):
        """
        Get classes in room for 1 week
        Function that requests information about classes for 1 day from today and returns list of dicts
        """

        needed_date = (datetime.today() + timedelta(days=10)).strftime(
            "%Y.%m.%d"
        )  # Не забыть поставить 1 день !!!!!!!!!!!!!!!!!

        params = dict(fromdate=needed_date, todate=needed_date, auditoriumoid=str(ruz_room_id))

        async with ClientSession() as session:
            res = await session.get(f"{self.url}/lessons", params=params)
            async with res:
                res = await res.json()

        classes = []
        for class_ in res:
            lesson = {}

            date = class_.pop("date")
            date = date.split(".")
            lesson["date"] = "-".join(date)

            lesson["start_time"] = class_.pop("beginLesson")
            lesson["end_time"] = class_.pop("endLesson")

            lesson["summary"] = class_["discipline"]
            lesson["location"] = f"{class_['auditorium']}/{class_['building']}"

            for key in class_:
                new_key = f"ruz_{camel_to_snake(key)}"
                lesson[new_key] = class_[key]

            lesson["ruz_url"] = lesson["ruz_url1"]

            if lesson["ruz_group"] is not None:
                stream = lesson["ruz_group"].split("#")[0]
                grp_emails = await nvr_api.get_course_emails(stream)
                if grp_emails is not None:
                    lesson["grp_emails"] = grp_emails
            else:
                stream = ""
            lesson["course_code"] = stream

            lesson["description"] = (
                f"Поток: {stream}\n"
                f"Преподаватель: {lesson['ruz_lecturer']}\n"
                f"Тип занятия: {lesson['ruz_kind_of_work']}\n"
            )

            if lesson["ruz_url"] and online:
                lesson["description"] += f"URL: {lesson['ruz_url']}\n"
                if lesson.get("ruz_lecturer_email"):  # None or ""
                    lesson["ruz_lecturer_email"] = (
                        lesson["ruz_lecturer_email"].split("@")[0] + "@miem.hse.ru"
                    )

            classes.append(lesson)

        return classes
