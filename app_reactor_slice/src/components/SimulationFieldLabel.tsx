import React, { useId } from "react";
import { Form, OverlayTrigger, Tooltip } from "react-bootstrap";

export function InfoTip({ text }: { text: React.ReactNode }) {
  const tipId = useId();
  return (
    <OverlayTrigger
      placement="right"
      container={typeof document !== "undefined" ? document.body : undefined}
      overlay={
        <Tooltip id={tipId} className="simulation-info-tooltip">
          {text}
        </Tooltip>
      }
    >
      <button type="button" className="simulation-info-btn" aria-label="More information" tabIndex={0}>
        <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="8" cy="5" r="1" fill="currentColor" />
          <path d="M8 7.2v4.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </OverlayTrigger>
  );
}

export function FieldLabel({
  children,
  info,
  className = "small mb-0",
}: {
  children: React.ReactNode;
  info?: React.ReactNode;
  className?: string;
}) {
  return (
    <Form.Label className={`${className} simulation-field-label d-inline-flex align-items-center gap-1`}>
      <span>{children}</span>
      {info != null ? <InfoTip text={info} /> : null}
    </Form.Label>
  );
}
