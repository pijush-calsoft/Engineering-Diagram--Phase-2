"""Block discovery through the ``edp.blocks`` entry point (plan section 3)."""

from importlib.metadata import entry_points

from edp_contracts.block import ENTRY_POINT_GROUP, Block


class NotABlockError(TypeError):
    pass


def discover_blocks() -> dict[str, Block]:
    """Load every registered block, keyed by its ``name``.

    An entry point may point at a block instance or a zero-argument class.
    """
    blocks: dict[str, Block] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        obj = ep.load()
        block = obj() if isinstance(obj, type) else obj
        if not isinstance(block, Block):
            raise NotABlockError(f"entry point {ep.name!r} does not implement Block")
        blocks[block.name] = block
    return blocks
