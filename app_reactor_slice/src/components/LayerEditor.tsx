import React, { useEffect, useRef, useState } from "react";
import type { LayerRow } from "../geometry";

type Props = {
  title: string;
  /** Name used when a material field is left blank. */
  fallback: string;
  rows: LayerRow[];
  lines: string[];
  onChange: (rows: LayerRow[]) => void;
  /** One material, no thickness and no extra rows. */
  single?: boolean;
  note?: string;
};

type Item = {
  id: string;
  name: string;
  cm: number;
  cmText: string;
};

const clampCm = (value: number) => {
  if (!Number.isFinite(value) || value < 0.01) return 0.1;
  if (value > 20) return 20;
  return Math.round(value * 10000) / 10000;
};

const signature = (rows: LayerRow[]) => JSON.stringify(rows.map((row) => [row.name, row.cm]));

const newId = () => Math.random().toString(36).slice(2, 10);

const toItems = (rows: LayerRow[]): Item[] =>
  rows.map((row) => ({ id: newId(), name: row.name, cm: row.cm, cmText: String(row.cm) }));

const LayerEditor: React.FC<Props> = ({ title, fallback, rows, lines, onChange, single = false, note }) => {
  const [items, setItems] = useState<Item[]>(() => toItems(rows));
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const itemsRef = useRef(items);
  const draggingRef = useRef<string | null>(null);
  const committed = useRef(signature(rows));
  const focusId = useRef<string | null>(null);
  itemsRef.current = items;

  const total = rows.reduce((sum, row) => sum + row.cm, 0);

  useEffect(() => {
    const incoming = signature(rows);
    if (incoming === committed.current) return;
    committed.current = incoming;
    setItems(toItems(rows));
  }, [rows]);

  useEffect(() => {
    if (!focusId.current || !listRef.current) return;
    const handle = listRef.current.querySelector<HTMLButtonElement>(
      `[data-id="${focusId.current}"] .layer-handle`,
    );
    focusId.current = null;
    handle?.focus();
  });

  const commit = (next: Item[]) => {
    const payload = next.map((item) => ({
      name: item.name.trim() || fallback,
      cm: clampCm(item.cm),
    }));
    committed.current = signature(payload);
    onChange(payload);
  };

  const patch = (id: string, change: Partial<Item>, publish: boolean) => {
    const next = itemsRef.current.map((item) => (item.id === id ? { ...item, ...change } : item));
    setItems(next);
    if (publish) commit(next);
  };

  const moveItem = (id: string, beforeId: string | null) => {
    const prev = itemsRef.current;
    const from = prev.findIndex((item) => item.id === id);
    if (from < 0) return;
    const moving = prev[from];
    const rest = prev.filter((item) => item.id !== id);
    const insertAt = beforeId == null ? rest.length : rest.findIndex((item) => item.id === beforeId);
    if (insertAt < 0) return;
    rest.splice(insertAt, 0, moving);
    if (rest.every((item, index) => item.id === prev[index].id)) return;
    itemsRef.current = rest;
    setItems(rest);
  };

  const onDragStart = (event: React.DragEvent<HTMLButtonElement>, id: string) => {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", id);
    draggingRef.current = id;
    setDraggingId(id);
  };

  const onDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const id = draggingRef.current;
    if (!id || !listRef.current) return;
    const nodes = [...listRef.current.querySelectorAll<HTMLElement>(".layer-row")];
    const others = nodes.filter((node) => node.dataset.id !== id);
    let beforeId: string | null = null;
    for (const node of others) {
      const box = node.getBoundingClientRect();
      if (event.clientY < box.top + box.height / 2) {
        beforeId = node.dataset.id ?? null;
        break;
      }
    }
    moveItem(id, beforeId);
  };

  const finishDrag = () => {
    if (!draggingRef.current) return;
    draggingRef.current = null;
    setDraggingId(null);
    commit(itemsRef.current);
  };

  const nudge = (event: React.KeyboardEvent<HTMLButtonElement>, id: string) => {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    const prev = itemsRef.current;
    const from = prev.findIndex((item) => item.id === id);
    const to = from + (event.key === "ArrowUp" ? -1 : 1);
    if (from < 0 || to < 0 || to >= prev.length) return;
    const next = [...prev];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    focusId.current = id;
    setItems(next);
    commit(next);
  };

  const add = () => {
    const next = [...itemsRef.current, { id: newId(), name: "Material", cm: 0.1, cmText: "0.1" }];
    setItems(next);
    commit(next);
  };

  const remove = (id: string) => {
    const next = itemsRef.current.filter((item) => item.id !== id);
    if (!next.length || itemsRef.current[0]?.id === id) return;
    setItems(next);
    commit(next);
  };

  return (
    <div className={`layer-editor${single ? " single" : ""}`}>
      <div className="layer-editor-title">
        {single ? title : `${title} · ${total.toFixed(2)} cm`}
      </div>
      {note && <div className="layer-editor-notes">{note}</div>}
      {!single && (
        <div className="layer-editor-labels">
          <span />
          <span>Material</span>
          <span>cm</span>
          <span />
        </div>
      )}
      <div ref={listRef} onDragOver={onDragOver} onDrop={(event) => event.preventDefault()}>
        {(single ? items.slice(0, 1) : items).map((item, index) => (
          <div
            key={item.id}
            className={`layer-row${draggingId === item.id ? " dragging" : ""}`}
            data-id={item.id}
          >
            {!single && (
              <button
                type="button"
                className="layer-handle"
                draggable
                title="Drag to reorder"
                aria-label="Drag to reorder"
                onDragStart={(event) => onDragStart(event, item.id)}
                onDragEnd={finishDrag}
                onKeyDown={(event) => nudge(event, item.id)}
              >
                ⋮⋮
              </button>
            )}
            <input
              className="layer-name"
              type="text"
              aria-label="Material"
              value={item.name}
              onChange={(event) => {
                const name = event.target.value;
                patch(item.id, { name }, Boolean(name.trim()));
              }}
              onBlur={() => {
                const current = itemsRef.current.find((entry) => entry.id === item.id);
                if (!current || current.name.trim()) return;
                patch(item.id, { name: fallback }, true);
              }}
            />
            {!single && (
              <input
                className="layer-cm"
                type="number"
                aria-label="cm"
                min={0.01}
                max={20}
                step={0.01}
                value={item.cmText}
                onChange={(event) => {
                  const cmText = event.target.value;
                  const value = event.target.valueAsNumber;
                  const inRange = Number.isFinite(value) && value >= 0.01 && value <= 20;
                  patch(item.id, { cmText, ...(inRange ? { cm: value } : {}) }, inRange);
                }}
                onBlur={(event) => {
                  const value = clampCm(event.currentTarget.valueAsNumber);
                  patch(item.id, { cm: value, cmText: String(value) }, true);
                }}
              />
            )}
            {!single && (
              <div className="layer-action">
                {index === 0 ? (
                  <span className="layer-base">base</span>
                ) : (
                  <button
                    type="button"
                    className="layer-remove"
                    title="Remove this material"
                    aria-label="Remove this material"
                    onClick={() => remove(item.id)}
                  >
                    ×
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {lines.length > 0 && (
        <div className="layer-editor-notes">
          {lines.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      )}
      {!single && (
        <button type="button" className="layer-add" onClick={add}>
          Add material
        </button>
      )}
    </div>
  );
};

export default LayerEditor;
