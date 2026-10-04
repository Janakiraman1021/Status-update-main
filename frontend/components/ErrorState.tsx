import { AlertTriangle } from "lucide-react";

import { Button } from "./ui";

export default function ErrorState({ title = "Unable to load this page", message, onRetry }: {
  title?: string; message?: string; onRetry?: () => void;
}) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center rounded-lg border border-danger/30 bg-danger-soft px-6 py-10 text-center">
      <AlertTriangle aria-hidden className="mb-2 h-5 w-5 text-danger" />
      <p className="text-sm font-semibold text-text">{title}</p>
      {message && <p className="mt-1 max-w-md text-[13px] text-muted">{message}</p>}
      {onRetry && (
        <Button className="mt-4" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
