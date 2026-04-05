from pydantic import BaseModel, Field


class TableItem(BaseModel):
    name: str = Field(description="Table or view name")
    kind: str = Field(description="'table' or 'view'")


class TableListResponse(BaseModel):
    items: list[TableItem]
    schema_name: str


class ColumnItem(BaseModel):
    name: str
    data_type: str
    is_nullable: bool
    ordinal_position: int
    suggested_field_type: str


class ColumnListResponse(BaseModel):
    items: list[ColumnItem]
    schema_name: str
    table_name: str
