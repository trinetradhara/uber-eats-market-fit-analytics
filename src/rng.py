"""Deterministic NumPy random-number streams."""

from numpy.random import Generator, SeedSequence, default_rng

from .config import CONFIG


class RNGStreams:
    """Provides stable independent streams for each generator module."""

    def __init__(self, seed: int = CONFIG.master_seed) -> None:
        sequence = SeedSequence(seed)
        names = (
            "markets", "entities", "behavior", "availability", "orders",
            "delivery", "experience", "promotions", "finance", "optional",
        )
        self._streams = dict(zip(names, map(default_rng, sequence.spawn(len(names)))))

    def for_module(self, module_name: str) -> Generator:
        """Return the stream assigned to a module."""
        if module_name not in self._streams:
            raise KeyError(f"Unknown RNG module: {module_name}")
        return self._streams[module_name]


def create_rngs(seed: int = CONFIG.master_seed) -> RNGStreams:
    """Create reproducible module-specific random streams."""
    return RNGStreams(seed)
