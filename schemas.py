from pydantic import BaseModel, Field, ConfigDict, field_validator

class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class StoreBaseModel(StrictBaseModel):
    store_id: str = Field(..., min_length=1)

class ProductItem(StrictBaseModel):
    name: str = Field(..., min_length=1)
    zone: str = Field(..., min_length=1)

class Supermarket(StoreBaseModel):
    items: list[str] = Field(..., min_length=1)

    @field_validator('items')
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        for item in value:
            if not item or len(item.strip()) == 0:
                raise ValueError("Item names cannot be empty strings")
        return value

class NewOrder(StoreBaseModel):
    item_name: str = Field(..., min_length=1)
    item_price: int = Field(..., ge=0)

    @field_validator('item_name')
    @classmethod
    def validate_item_name(cls, value: str) -> str:
        if not value or len(value.strip()) == 0:
            raise ValueError("Item name cannot be an empty string")
        return value

class SubstitutionRequest(StrictBaseModel):
    missing_item: str = Field(..., min_length=1)

class MultiOrderRequest(StoreBaseModel):
    orders: list[list[str]] = Field(..., min_length=1)

    @field_validator('orders')
    @classmethod
    def validate_orders(cls, value: list[list[str]]) -> list[list[str]]:
        for basket in value:
            if not basket or len(basket) == 0:
                raise ValueError("Individual order baskets cannot be empty")
            for item in basket:
                if not item or len(item.strip()) == 0:
                    raise ValueError("Item names inside baskets cannot be empty strings")
        return value