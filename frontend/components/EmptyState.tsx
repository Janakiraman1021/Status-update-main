import { Inbox } from "lucide-react";

export default function EmptyState({ title, description, action, icon }: {
  title: string; description?: React.ReactNode; action?: React.ReactNode; icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 rounded-full bg-surface-hover p-2.5 text-subtle" aria-hidden>
        {icon ?? <Inbox className="h-5 w-5" />}
      </div>
      <p className="text-sm font-medium text-text">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[13px] text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
