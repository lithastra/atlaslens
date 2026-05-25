from pydantic import BaseModel, Field


class AccountLink(BaseModel):
    deployment: str
    product: str
    external_id: str


class Identity(BaseModel):
    id: str = Field(alias="_id")
    display_name: str
    emails: list[str] = Field(default_factory=list)
    accounts: list[AccountLink] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
