from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    cassandra_contact_points: str = "localhost"
    cassandra_port: int = 9042
    cassandra_username: str = ""
    cassandra_password: str = ""
    cassandra_keyspace: str = "retail_risk"
    janusgraph_gremlin_endpoint: str = "ws://localhost:8182/gremlin"
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "retail-risk"
    iceberg_catalog_type: str = "nessie"
    iceberg_warehouse: str = "s3://retail-risk/warehouse"
    iceberg_catalog_name: str = "default"
    iceberg_namespace: str = "risk"
    trino_host: str = "localhost"
    trino_port: int = 8080
    trino_catalog: str = "iceberg"
    trino_schema: str = "default"
    trino_user: str = "risk-user"
    vector_index_bucket_path: str = "s3://retail-risk/indices"
    model_version: str = "v1"
    rng_seed: int = 42


def get_settings() -> Settings:
    return Settings()
