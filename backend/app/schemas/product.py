from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    brand_name: str = Field(default="", max_length=100)
    category: str = Field(default="", max_length=100)
    sku: str = Field(default="", max_length=100)
    price_cent: int = Field(default=0, ge=0)
    activity_price_cent: int = Field(default=0, ge=0)
    parameter: dict = Field(default_factory=dict)
    selling_point: dict = Field(default_factory=dict)
    ai_material: dict = Field(default_factory=dict)


class MaterialPackageCreate(BaseModel):
    package_name: str = Field(min_length=1, max_length=100)
    package_type: str = Field(default="", max_length=50)
    remark: str = Field(default="", max_length=500)
