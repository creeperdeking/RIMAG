"""Drag-to-reorder material list for one layer stack.

Registered in this module so Streamlit does not re-register it on every rerun.
"""

from __future__ import annotations

import streamlit as st

_HTML = """
<div class="labels"><span></span><span>Material</span><span>cm</span><span></span></div>
<div id="list"></div>
"""

_CSS = """
:host {
  color: var(--st-text-color);
  font: inherit;
}
.labels, .row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1.8fr) minmax(0, 0.9fr) 44px;
  gap: 0.35rem;
  align-items: center;
}
.labels {
  font-weight: 600;
  margin: 0 0 0.3rem;
}
.row {
  margin-bottom: 0.4rem;
}
.row.dragging {
  opacity: 0.45;
}
.handle, .remove {
  border: none;
  background: transparent;
  color: var(--st-text-color);
  padding: 0.15rem;
}
.handle {
  cursor: grab;
  opacity: 0.55;
  touch-action: none;
  font-size: 1.05rem;
  line-height: 1;
}
.handle:active {
  cursor: grabbing;
}
.handle:focus-visible, .remove:focus-visible, input:focus {
  outline: 2px solid var(--st-primary-color);
  outline-offset: 1px;
}
.remove {
  cursor: pointer;
  font-size: 1.15rem;
}
.base {
  text-align: center;
  font-size: 0.8rem;
  opacity: 0.65;
}
input {
  width: 100%;
  box-sizing: border-box;
  background: var(--st-background-color);
  color: var(--st-text-color);
  border: 1px solid var(--st-widget-border-color, var(--st-border-color));
  border-radius: var(--st-base-radius, 0.5rem);
  padding: 0.4rem 0.55rem;
  font: inherit;
}
"""

_JS = """
export default function (component) {
  const { data, parentElement, setStateValue } = component
  const list = parentElement.querySelector("#list")
  if (!list || list.dataset.dragging === "1") return

  const fallback = (data && data.fallback) || "Material"
  const rows = (data && data.rows) || []
  const emit = () => setStateValue("rows", readRows(list, fallback))

  if (!sameRows(list, rows)) {
    list.replaceChildren()
    rows.forEach((row) => list.appendChild(makeRow(row, fallback, emit)))
  }
  list.ondragover = (event) => {
    event.preventDefault()
    const dragging = list.querySelector(".dragging")
    if (!dragging) return
    const after = rowAfter(list, event.clientY, dragging)
    if (after) list.insertBefore(dragging, after)
    else list.appendChild(dragging)
  }
  list.ondrop = (event) => event.preventDefault()
  refreshActions(list, emit)
}

function sameRows(list, rows) {
  const current = [...list.querySelectorAll(".row")]
  if (current.length !== rows.length) return false
  return current.every((element, index) => {
    const name = element.querySelector(".name").value
    const cm = Number(element.querySelector(".cm").value)
    const wanted = Number(rows[index].cm)
    return name === String(rows[index].name ?? "") && Number.isFinite(cm) && Math.abs(cm - wanted) < 0.00005
  })
}

function readRows(list, fallback) {
  return [...list.querySelectorAll(".row")].map((element) => {
    const name = element.querySelector(".name").value.trim() || fallback
    let cm = Number(element.querySelector(".cm").value)
    if (!Number.isFinite(cm)) cm = 0.1
    cm = Math.min(20, Math.max(0.01, cm))
    return { name, cm }
  })
}

function makeRow(row, fallback, emit) {
  const element = document.createElement("div")
  element.className = "row"

  const handle = document.createElement("button")
  handle.type = "button"
  handle.className = "handle"
  handle.textContent = "⋮⋮"
  handle.title = "Drag to reorder"
  handle.draggable = true
  handle.setAttribute("aria-label", "Drag to reorder")
  handle.ondragstart = (event) => {
    element.classList.add("dragging")
    element.parentElement.dataset.dragging = "1"
    event.dataTransfer.effectAllowed = "move"
    event.dataTransfer.setData("text/plain", "row")
  }
  handle.ondragend = () => {
    element.classList.remove("dragging")
    const parent = element.parentElement
    if (parent) delete parent.dataset.dragging
    refreshActions(parent, emit)
    emit()
  }
  handle.onkeydown = (event) => nudge(event, element, emit)

  const name = document.createElement("input")
  name.className = "name"
  name.type = "text"
  name.setAttribute("aria-label", "Material")
  name.value = String(row.name ?? "")
  name.oninput = () => {
    if (name.value.trim()) emit()
  }
  name.onblur = () => {
    if (!name.value.trim()) name.value = fallback
    emit()
  }

  const cm = document.createElement("input")
  cm.className = "cm"
  cm.type = "number"
  cm.min = "0.01"
  cm.max = "20"
  cm.step = "0.01"
  cm.setAttribute("aria-label", "cm")
  cm.value = String(row.cm ?? "")
  cm.oninput = () => {
    const value = Number(cm.value)
    if (Number.isFinite(value) && value >= 0.01 && value <= 20) emit()
  }
  cm.onblur = () => {
    const value = Number(cm.value)
    if (!Number.isFinite(value) || value < 0.01) cm.value = "0.10"
    else if (value > 20) cm.value = "20"
    emit()
  }

  const action = document.createElement("div")
  action.className = "action"
  element.append(handle, name, cm, action)
  return element
}

function refreshActions(list, emit) {
  const rows = [...list.querySelectorAll(".row")]
  rows.forEach((element, index) => {
    const action = element.querySelector(".action")
    action.replaceChildren()
    if (index === 0) {
      const base = document.createElement("span")
      base.className = "base"
      base.textContent = "base"
      action.appendChild(base)
      return
    }
    const remove = document.createElement("button")
    remove.type = "button"
    remove.className = "remove"
    remove.textContent = "×"
    remove.title = "Remove this material"
    remove.setAttribute("aria-label", "Remove this material")
    remove.onclick = () => {
      element.remove()
      refreshActions(list, emit)
      emit()
    }
    action.appendChild(remove)
  })
}

function rowAfter(list, y, dragging) {
  const rows = [...list.querySelectorAll(".row")].filter((row) => row !== dragging)
  for (const row of rows) {
    const box = row.getBoundingClientRect()
    if (y < box.top + box.height / 2) return row
  }
  return null
}

function nudge(event, element, emit) {
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return
  event.preventDefault()
  const list = element.parentElement
  if (event.key === "ArrowUp" && element.previousElementSibling) {
    list.insertBefore(element, element.previousElementSibling)
  } else if (event.key === "ArrowDown" && element.nextElementSibling) {
    list.insertBefore(element.nextElementSibling, element)
  } else {
    return
  }
  refreshActions(list, emit)
  element.querySelector(".handle").focus()
  emit()
}
"""

_LIST = st.components.v2.component(
    "layer_material_list",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def _list_key(group_id: str) -> str:
    epoch = int(st.session_state.get("layer_epoch", 0))
    return f"layer_list_{epoch}_{group_id}"


def _apply_rows(group_id: str, fallback: str) -> None:
    """Copy a dragged or edited list into the stack, keeping at least one row."""
    state = st.session_state.get(_list_key(group_id), {})
    raw = state.get("rows") if isinstance(state, dict) else None
    if not isinstance(raw, list) or not raw:
        return
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip() or fallback
        try:
            cm = float(item.get("cm"))
        except (TypeError, ValueError):
            continue
        cleaned.append({"name": name, "cm": round(min(20.0, max(0.01, cm)), 4)})
    if cleaned:
        st.session_state.groups[group_id] = cleaned


def mount_layer_list(group_id: str, title: str, rows: list[dict]) -> None:
    """Show one stack. Dragging a row updates that stack before the chart is drawn."""
    payload = [
        {"name": str(row.get("name", title)), "cm": float(row.get("cm", 0.1))}
        for row in rows
    ]
    _LIST(
        key=_list_key(group_id),
        data={"rows": payload, "fallback": title},
        on_rows_change=lambda gid=group_id, fallback=title: _apply_rows(gid, fallback),
        width="stretch",
        height="content",
    )
