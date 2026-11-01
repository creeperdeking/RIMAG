#!/usr/bin/env python3
"""Open the staged OpenMC model in openmc-plotter using materials.py colors."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openmc.plots import _SVG_COLORS
from openmc_plotter.__main__ import main
from openmc_plotter.plotmodel import PlotView

from common_lib.materials import color_for_openmc_material_name

_ORIGINAL_GET_DOMAINS = PlotView.getDomains


def _apply_material_colors(domains):
    """Color materials from materials.py.

    DomainViewDict stores the initial colors in ``defaults`` and leaves the
    dict itself empty. Iterating ``domains.items()`` therefore sees nothing,
    and the random colors stay on screen.
    """
    defined = getattr(domains, "defaults", domains)
    for domain_id, view in list(defined.items()):
        # The plotter's own "VOID" entry is empty space, not the Void material.
        if view.name == "VOID":
            continue
        svg_color = color_for_openmc_material_name(view.name).lower()
        rgb = _SVG_COLORS.get(svg_color)
        if rgb is None:
            continue
        rgb = tuple(int(channel) for channel in rgb)
        view.color = rgb
        domains.set_color(domain_id, rgb)
    return domains


def _get_domains(domain_type, rng):
    domains = _ORIGINAL_GET_DOMAINS(domain_type, rng)
    if domain_type != "material":
        return domains
    return _apply_material_colors(domains)


PlotView.getDomains = staticmethod(_get_domains)


if __name__ == "__main__":
    model_path = sys.argv[1] if len(sys.argv) > 1 else "."
    # -e ignores plot_settings.pkl so a previous random palette is not restored.
    sys.argv = [sys.argv[0], "-e", model_path]
    main()
