from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "atlaslens"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    encryption_key: str = ""

    atlassian_site: str = ""
    atlassian_org_id: str = ""
    atlassian_email: str = ""
    atlassian_api_token: str = ""
    atlassian_oauth_client_id: str = ""
    atlassian_oauth_client_secret: str = ""

    bitbucket_workspace: str = ""
    bitbucket_app_password: str = ""

    ingest_interval_minutes: int = 15

    model_config = {"env_prefix": "ATLASLENS_", "env_file": ".env"}


settings = Settings()
