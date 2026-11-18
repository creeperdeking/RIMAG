import React from "react";
import { Button, Form } from "react-bootstrap";
import type { LayerRow } from "../geometry";

type Props = {
  title: string;
  rows: LayerRow[];
  materialOptions: string[];
  onChange: (rows: LayerRow[]) => void;
};

const LayerEditor: React.FC<Props> = ({ title, rows, materialOptions, onChange }) => {
  const total = rows.reduce((sum, row) => sum + row.cm, 0);

  const update = (index: number, patch: Partial<LayerRow>) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const move = (index: number, direction: -1 | 1) => {
    const next = index + direction;
    if (next < 0 || next >= rows.length) return;
    const copy = [...rows];
    const [item] = copy.splice(index, 1);
    copy.splice(next, 0, item);
    onChange(copy);
  };

  const remove = (index: number) => {
    if (rows.length <= 1) return;
    onChange(rows.filter((_, i) => i !== index));
  };

  return (
    <div className="border rounded p-3 bg-white mb-3">
      <div className="fw-semibold mb-2">
        {title} · {total.toFixed(2)} cm
      </div>
      {rows.map((row, index) => (
        <div key={`${title}-${index}`} className="d-flex flex-wrap gap-2 align-items-center mb-2">
          <div className="btn-group btn-group-sm">
            <Button variant="outline-secondary" size="sm" onClick={() => move(index, -1)} disabled={index === 0}>
              ↑
            </Button>
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={() => move(index, 1)}
              disabled={index === rows.length - 1}
            >
              ↓
            </Button>
          </div>
          <Form.Select
            size="sm"
            style={{ maxWidth: 220 }}
            value={materialOptions.includes(row.name) ? row.name : ""}
            onChange={(event) => update(index, { name: event.target.value || row.name })}
          >
            {!materialOptions.includes(row.name) && <option value={row.name}>{row.name}</option>}
            {materialOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Form.Select>
          <Form.Control
            size="sm"
            type="number"
            min={0.01}
            max={20}
            step={0.01}
            value={row.cm}
            style={{ maxWidth: 96 }}
            onChange={(event) => {
              const cm = Number(event.target.value);
              if (!Number.isFinite(cm)) return;
              update(index, { cm: Math.min(20, Math.max(0.01, cm)) });
            }}
          />
          <span className="small text-secondary">cm</span>
          <Button variant="outline-danger" size="sm" onClick={() => remove(index)} disabled={rows.length <= 1}>
            Remove
          </Button>
        </div>
      ))}
      <Button
        size="sm"
        variant="outline-primary"
        onClick={() => onChange([...rows, { name: "Material", cm: 0.1 }])}
      >
        Add material
      </Button>
    </div>
  );
};

export default LayerEditor;
