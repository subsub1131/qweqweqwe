"""Process-local demo data. Restarting the server discards registrations/purchases."""
from threading import RLock
from uuid import uuid4
from app.schemas.course import Course, CourseInput, DemoPurchase

INSTRUCTOR = "봄날 선생님"

class CourseDemoRepository:
    def __init__(self):
        self._lock = RLock()
        self._courses: dict[int, Course] = {}
        self._purchases: dict[tuple[str, int], DemoPurchase] = {}
        samples = (
            ("파이썬 첫걸음", "기초 문법부터 작은 프로그램까지 함께 만듭니다.", "개발", 39000, 180, 12),
            ("감각을 담은 웹 디자인", "색과 여백으로 나만의 웹 화면을 구성합니다.", "디자인", 49000, 150, 10),
            ("일상을 기록하는 사진", "빛과 구도를 배워 일상의 순간을 남깁니다.", "라이프", 29000, 120, 8),
            ("처음 시작하는 글쓰기", "나의 생각을 짧고 명확한 글로 표현합니다.", "글쓰기", 35000, 100, 7),
        )
        for title, description, category, price, duration, lessons in samples:
            self.create(CourseInput(title=title, description=description, category=category,
                                    price=price, duration_minutes=duration, lesson_count=lessons))

    def list_courses(self) -> list[Course]:
        with self._lock:
            return list(self._courses.values())

    def get(self, course_id: int) -> Course | None:
        with self._lock:
            return self._courses.get(course_id)

    def create(self, data: CourseInput) -> Course:
        with self._lock:
            course_id = max(self._courses, default=0) + 1
            course = Course(id=course_id, instructor=INSTRUCTOR, **data.model_dump())
            self._courses[course_id] = course
            return course

    def purchase(self, owner: str, course_id: int) -> tuple[DemoPurchase, bool]:
        with self._lock:
            course = self._courses.get(course_id)
            if course is None:
                raise KeyError(course_id)
            key = (owner, course_id)
            if key in self._purchases:
                return self._purchases[key], False
            purchase = DemoPurchase(id=str(uuid4()), course=course)
            self._purchases[key] = purchase
            return purchase, True

    def purchased_courses(self, owner: str) -> list[Course]:
        with self._lock:
            return [purchase.course for (buyer, _), purchase in self._purchases.items() if buyer == owner]

    def restore_snapshots(self, courses):
        with self._lock:
            for course in courses:
                self._courses[course.id] = course
