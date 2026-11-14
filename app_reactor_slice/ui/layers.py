"""Layer-stack session state, thickness checks, and saved configurations."""

from __future__ import annotations

import json

import streamlit as st

from configurations import (
    LAYER_IDS,
    NUMERIC_FIELDS,
    ConfigurationError,
    delete_configuration,
    list_configurations,
    load_configuration,
    save_configuration,
)
from constants import EDITOR_GROUPS, LAYER_GROUPS


def default_groups() -> dict[str, list[dict]]:
    return {
        group_id: [{"name": title, "cm": 1.0}]
        for group_id, title, _colors in EDITOR_GROUPS
    }


def _is_placeholder_stack(rows: list[dict], title: str) -> bool:
    """The one-centimeter titled row used when a stack is missing from the address."""
    return (
        len(rows) == 1
        and rows[0].get("name") == title
        and abs(float(rows[0].get("cm", 0)) - 1.0) < 1e-6
    )


def _layers_from_saved_configuration() -> dict[str, list[dict]] | None:
    """Layers of the configuration named in the address, or the only saved one."""
    cfg = st.query_params.get("cfg")
    if not cfg:
        names = list_configurations()
        cfg = names[0] if len(names) == 1 else None
    if not cfg:
        return None
    try:
        layers = load_configuration(cfg)["layers"]
    except ConfigurationError:
        return None
    st.session_state.loaded_cfg = cfg
    return layers


def initial_groups() -> dict[str, list[dict]]:
    raw = st.query_params.get("layers")
    groups = None
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            groups = {}
            address_has_disk = False
            for group_id, title, _colors in EDITOR_GROUPS:
                rows = data.get(group_id) or []
                try:
                    parsed = [{"name": str(item["n"]), "cm": float(item["cm"])} for item in rows]
                except (KeyError, TypeError, ValueError):
                    parsed = []
                if parsed and all(row["cm"] > 0 for row in parsed):
                    groups[group_id] = parsed
                    if group_id == "disk":
                        address_has_disk = True
                else:
                    groups[group_id] = [{"name": title, "cm": 1.0}]
    if groups is None:
        groups = default_groups()
        address_has_disk = False
    # A reload keeps the old address. Stacks that are still the titled 1 cm
    # placeholder are replaced from the save so they match the file.
    saved = _layers_from_saved_configuration()
    if saved:
        for group_id, title, _colors in EDITOR_GROUPS:
            if _is_placeholder_stack(groups[group_id], title) and saved.get(group_id):
                groups[group_id] = [dict(row) for row in saved[group_id]]
    if not address_has_disk:
        _drop_repeated_disk(groups)
    return groups


def _drop_repeated_disk(groups: dict[str, list[dict]]) -> None:
    """Remove a copied void / disk / void tail once the disk has its own list."""
    disk = groups.get("disk") or []
    if not disk:
        return
    for group_id, _title, _colors in LAYER_GROUPS:
        rows = groups.get(group_id) or []
        if len(rows) > len(disk) and same_layers(rows[-len(disk) :], disk):
            groups[group_id] = rows[: -len(disk)]


def same_layers(left: list[dict], right: list[dict]) -> bool:
    if len(left) != len(right):
        return False
    for one, other in zip(left, right):
        if one.get("name") != other.get("name"):
            return False
        if abs(float(one.get("cm", 0)) - float(other.get("cm", 0))) > 1e-4:
            return False
    return True


def bump_layer_widgets() -> None:
    """Drop the current layer widgets so the next run builds them from groups."""
    st.session_state.layer_epoch = int(st.session_state.get("layer_epoch", 0)) + 1
    for key in list(st.session_state):
        if key.startswith(("lname_", "lcm_")):
            del st.session_state[key]


def sync_groups_from_widgets() -> None:
    if "groups" not in st.session_state:
        st.session_state.groups = initial_groups()
        return
    groups = st.session_state.groups
    for group_id, title, _colors in EDITOR_GROUPS:
        if not groups.get(group_id):
            groups[group_id] = [{"name": title, "cm": 1.0}]
    st.session_state.groups = groups


def add_layer(group_id: str) -> None:
    st.session_state.groups[group_id].append({"name": "Material", "cm": 0.1})


def group_thicknesses(groups: dict[str, list[dict]]) -> list[tuple[str, float]]:
    """Total cm of each zone stack plus the shared disk, from fuel through TPV."""
    disk_cm = sum(layer["cm"] for layer in groups.get("disk") or [])
    return [
        (title, sum(layer["cm"] for layer in groups[group_id]) + disk_cm)
        for group_id, title, _colors in LAYER_GROUPS
    ]


def shared_thickness(totals: list[tuple[str, float]]) -> float | None:
    """The common thickness when every layer matches to the nearest 0.01 cm."""
    if len({round(cm, 2) for _title, cm in totals}) != 1:
        return None
    return totals[0][1]


def thickness_warning(totals: list[tuple[str, float]]) -> str:
    parts = [f"{title} is {cm:.2f} cm" for title, cm in totals]
    return ", ".join(parts[:-1]) + ", and " + parts[-1] + "."


def snapshot_configuration() -> dict:
    """Sidebar values and layer stacks."""
    layers = {}
    groups = st.session_state.get("groups") or {}
    for group_id in LAYER_IDS:
        rows = groups.get(group_id) or []
        layers[group_id] = [
            {"name": row.get("name"), "cm": row.get("cm")}
            for row in rows
        ]
    data = {key: st.session_state.get(key) for key in NUMERIC_FIELDS}
    data["reload_fraction"] = st.session_state.get("reload_fraction", "1/4")
    data["dims"] = bool(st.session_state.get("dims", True))
    data["layers"] = layers
    return data


def apply_configuration(data: dict) -> None:
    """Install a loaded configuration before the sidebar widgets are created."""
    for key in NUMERIC_FIELDS:
        st.session_state[key] = data[key]
    st.session_state.reload_fraction = data["reload_fraction"]
    st.session_state.dims = data["dims"]
    st.session_state.groups = data["layers"]
    bump_layer_widgets()


def on_save_configuration() -> None:
    try:
        path = save_configuration(st.session_state.get("save_name", ""), snapshot_configuration())
    except ConfigurationError as error:
        st.session_state.config_notice = ("error", str(error))
        return
    st.session_state.load_choice = path.stem
    st.session_state.config_notice = ("success", f"Saved {path.stem}.")


@st.dialog("Delete configuration")
def confirm_delete_configuration(name: str) -> None:
    st.write(f"Delete {name} from the save folder?")
    confirm, cancel = st.columns(2)
    if confirm.button("Delete", key="confirm_delete_config", type="primary"):
        try:
            deleted = delete_configuration(name)
        except ConfigurationError as error:
            st.error(str(error))
            return
        st.session_state.config_notice = ("success", f"Deleted {deleted}.")
        st.rerun()
    if cancel.button("Cancel", key="cancel_delete_config"):
        st.rerun()


def on_load_configuration() -> None:
    choice = st.session_state.get("load_choice")
    if not choice:
        st.session_state.config_notice = ("error", "Choose a saved configuration.")
        return
    try:
        data = load_configuration(choice)
    except ConfigurationError as error:
        st.session_state.config_notice = ("error", str(error))
        return
    apply_configuration(data)
    st.session_state.loaded_cfg = choice
    st.session_state.config_notice = ("success", f"Loaded {choice}.")
