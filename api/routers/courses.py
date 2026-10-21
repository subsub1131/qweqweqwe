"""Minimal course catalog and authenticated demo purchase routes."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from api.deps import current_account, require_same_origin
from app.core.security import session_account_binding
from app.core.config import settings
from app.services.portone import get_payment_service
from app.schemas.course import Course, CourseInput, CourseList, DemoPurchase, PurchaseInput
from app.services.course_demo import CourseDemoRepository

router = APIRouter(prefix="/api", tags=["course-demo"])
repository = CourseDemoRepository()

def require_demo_origin(request: Request):
    if request.headers.get("origin") is None:
        raise HTTPException(status_code=403, detail="Request origin is required.")
    require_same_origin(request)

def owner_key(identity):
    provider, account = identity
    return session_account_binding(provider, account)

@router.get("/courses", response_model=CourseList)
def list_courses(service=Depends(get_payment_service)):
    if settings.PORTONE_ENABLED:
        service.restore_catalog(repository)
    return CourseList(items=repository.list_courses())

@router.get("/courses/{course_id}", response_model=Course)
def course_detail(course_id: int, service=Depends(get_payment_service)):
    if settings.PORTONE_ENABLED:
        service.restore_catalog(repository)
    course = repository.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course

@router.post("/demo/courses", response_model=Course, status_code=201,
             dependencies=[Depends(require_demo_origin)])
def create_course(data: CourseInput, response: Response, identity=Depends(current_account), service=Depends(get_payment_service)):
    response.headers["Cache-Control"] = "no-store"
    if settings.PORTONE_ENABLED:
        service.restore_catalog(repository)
    return repository.create(data)

@router.post("/demo/purchases", response_model=DemoPurchase, status_code=201,
             dependencies=[Depends(require_demo_origin)])
def purchase_course(data: PurchaseInput, response: Response, identity=Depends(current_account)):
    if settings.PORTONE_ENABLED:
        raise HTTPException(status_code=403, detail="Demo purchases are disabled for test payments.")
    try:
        purchase, created = repository.purchase(owner_key(identity), data.course_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Course not found.") from None
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    return purchase

@router.get("/my/courses", response_model=CourseList)
def my_courses(response: Response, identity=Depends(current_account), service=Depends(get_payment_service)):
    response.headers["Cache-Control"] = "no-store"
    if settings.PORTONE_ENABLED:
        return CourseList(items=service.purchased_courses(owner_key(identity)))
    return CourseList(items=repository.purchased_courses(owner_key(identity)))
