"""Desktop entry point and configuration commands exposed to Svelte."""

from anyio import to_thread
from anyio.from_thread import start_blocking_portal
from pytauri import Commands, builder_factory, context_factory
from pytauri.ipc import InvokeException
from pydantic import BaseModel

import json
from typing import Optional

from .main import RegressionPayload, execute_regression as execute_regression_service
from .services.acquisition import acquire
from .services.appeears import catalog as appeears_catalog
from .services.assistant import AssistantQuestion, interpret
from .services.assistant_providers import Connection, configure_connection, connection_status, forget_connection
from .services.evidence import with_evidence
from .services.coverage import CoverageRequest, coverage
from .services.public_sources import find_places
from .services.station_catalogs import ina_variables

from .configuration import (
    ConfigurationName,
    ConfigurationSnapshot,
    read_configuration,
    write_configurations,
)

commands: Commands = Commands()


@commands.command()
async def load_configuration(body: ConfigurationName) -> str:
    return await to_thread.run_sync(read_configuration, body.name)


@commands.command()
async def save_configuration(body: ConfigurationSnapshot) -> bool:
    await to_thread.run_sync(write_configurations, body)
    return True


class AcquisitionRequest(BaseModel):
    investigation: dict


@commands.command()
async def acquire_data(body: AcquisitionRequest) -> str:
    try:
        series = await to_thread.run_sync(lambda: with_evidence(acquire(body.investigation)))
    except ValueError as error:
        raise InvokeException(str(error)) from error
    return json.dumps(series, allow_nan=False)


class AppEEARSCatalogRequest(BaseModel):
    product: Optional[str] = None


@commands.command()
async def list_appeears(body: AppEEARSCatalogRequest) -> list:
    try:
        return await to_thread.run_sync(appeears_catalog, body.product)
    except ValueError as error:
        raise InvokeException(str(error)) from error


@commands.command()
async def list_ina_variables() -> list:
    try:
        return await to_thread.run_sync(ina_variables)
    except ValueError as error:
        raise InvokeException(str(error)) from error


class PlaceRequest(BaseModel):
    query: str
    kind: str
    language: str = "es"


@commands.command()
async def search_places(body: PlaceRequest) -> str:
    try:
        places = await to_thread.run_sync(find_places, body.query, body.kind, body.language)
    except ValueError as error:
        raise InvokeException(str(error)) from error
    return json.dumps(places, allow_nan=False)


@commands.command()
async def execute_regression(body: RegressionPayload) -> dict:
    return await to_thread.run_sync(execute_regression_service, body)


@commands.command()
async def evaluate_coverage(body: CoverageRequest) -> dict:
    return {"matches": coverage(body)}


@commands.command()
async def interpret_question(body: AssistantQuestion) -> dict:
    try:
        return await to_thread.run_sync(interpret, body)
    except ValueError as error:
        raise InvokeException(str(error)) from error


@commands.command()
async def assistant_status() -> dict:
    return connection_status()


@commands.command()
async def configure_assistant(body: Connection) -> dict:
    try:
        return await to_thread.run_sync(configure_connection, body)
    except ValueError as error:
        raise InvokeException(str(error)) from error


@commands.command()
async def disconnect_assistant() -> dict:
    return forget_connection()


def main() -> int:
    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=context_factory(),
            invoke_handler=commands.generate_handler(portal),
        )
        return app.run_return()
