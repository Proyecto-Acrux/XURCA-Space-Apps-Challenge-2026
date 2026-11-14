
"""Desktop entry point and configuration commands exposed to Svelte."""
"""
from anyio import to_thread
from anyio.from_thread import start_blocking_portal
from pytauri import Commands, builder_factory, context_factory

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


def main() -> int:
    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=context_factory(),
            invoke_handler=commands.generate_handler(portal),
        )
        return app.run_return()
"""

"""PyTauri application entry point."""

from anyio import to_thread
from anyio.from_thread import start_blocking_portal
from pytauri import Commands, builder_factory, context_factory

from trend_scope.configuration import (
    ConfigurationName,
    ConfigurationSnapshot,
    read_configuration,
    write_configurations,
)
from trend_scope.main import (
    RegressionPayload,
    execute_regression as execute_regression_service,
)


commands: Commands = Commands()


@commands.command()
async def load_configuration(body: ConfigurationName) -> str:
    return await to_thread.run_sync(read_configuration, body.name)


@commands.command()
async def save_configuration(body: ConfigurationSnapshot) -> bool:
    await to_thread.run_sync(write_configurations, body)
    return True


@commands.command()
def execute_regression(payload: RegressionPayload) -> dict:
    return execute_regression_service(payload)


def main() -> int:
    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=context_factory(),
            invoke_handler=commands.generate_handler(portal),
        )

        return app.run_return()


if __name__ == "__main__":
    raise SystemExit(main())
