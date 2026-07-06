from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.product_repository import ProductRepository
from app.schemas.product import MaterialPackageCreate, ProductCreate


router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("")
def create_product(
    payload: ProductCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ProductRepository(conn)
    product_id = repo.create_product(user["id"], payload)
    return ok(repo.get_for_user(user["id"], product_id))


@router.get("")
def list_products(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ProductRepository(conn)
    return ok(repo.list_products(user["id"]))


@router.get("/{product_id}")
def get_product(
    product_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ProductRepository(conn)
    product = repo.get_for_user(user["id"], product_id)
    if product is None:
        return _product_not_found()
    return ok(product)


@router.post("/{product_id}/material-packages")
def create_material_package(
    product_id: int,
    payload: MaterialPackageCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ProductRepository(conn)
    try:
        package_id = repo.create_material_package(user["id"], product_id, payload)
        package = repo.get_material_package_for_user(user["id"], product_id, package_id)
    except ValueError:
        return _product_not_found()

    if package is None:
        return _product_not_found()
    return ok(package)


@router.get("/{product_id}/material-packages")
def list_material_packages(
    product_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ProductRepository(conn)
    try:
        packages = repo.list_material_packages(user["id"], product_id)
    except ValueError:
        return _product_not_found()
    return ok(packages)


def _product_not_found() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=fail("NOT_FOUND", "product not found"),
    )
