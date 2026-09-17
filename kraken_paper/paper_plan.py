from __future__ import annotations

from kraken_paper.models import PairInfo, Setup, SizePlan
from kraken_paper.sizing import size_long, translate_live_to_paper


class NoAPlusError(RuntimeError):
    pass


def plans_from_setup(setup: Setup, meta: PairInfo | None = None) -> tuple[SizePlan, SizePlan]:
    if not setup.tradable or setup.entry is None or setup.stop is None:
        raise NoAPlusError(
            "No A+ setup to size. The locked book does not send B/A/SKIP clips. "
            "Use `scan` to see why each pair was skipped."
        )
    kwargs = {}
    if meta is not None:
        kwargs = {
            "pair_decimals": meta.pair_decimals,
            "lot_decimals": meta.lot_decimals,
            "ordermin": meta.ordermin,
        }
    live = size_long(setup.entry, setup.stop, book="live", t1=setup.t1, t2=setup.t2, **kwargs)
    paper = translate_live_to_paper(live)
    return live, paper
