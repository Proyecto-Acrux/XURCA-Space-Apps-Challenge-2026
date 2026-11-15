"""Earth Detective scientific services and desktop entry point."""


def main() -> int:
    from .desktop import main as run_desktop

    return run_desktop()
