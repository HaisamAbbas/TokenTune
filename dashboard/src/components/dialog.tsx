"use client";

import * as RadixDialog from "@radix-ui/react-dialog";

export function Dialog({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "oklch(0% 0 0 / 0.4)",
          }}
        />
        <RadixDialog.Content
          className="panel"
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 480,
            maxWidth: "calc(100vw - 32px)",
            maxHeight: "85vh",
            overflow: "auto",
            padding: 28,
          }}
        >
          <RadixDialog.Title className="t-title" style={{ marginBottom: 18 }}>
            {title}
          </RadixDialog.Title>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
