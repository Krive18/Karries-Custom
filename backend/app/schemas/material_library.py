from pydantic import BaseModel, Field


class MaterialProjectGroupCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=80)


class MaterialProjectGroupRename(BaseModel):
    group_name: str = Field(min_length=1, max_length=80)


class MaterialFolderCreate(BaseModel):
    project_group_id: int = Field(default=0, ge=0)
    parent_id: int = Field(default=0, ge=0)
    folder_name: str = Field(min_length=1, max_length=100)


class MaterialFolderRename(BaseModel):
    folder_name: str = Field(min_length=1, max_length=100)


class MaterialAssetUpdate(BaseModel):
    folder_id: int | None = Field(default=None, ge=0)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
