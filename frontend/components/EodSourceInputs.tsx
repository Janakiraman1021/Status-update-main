import type { EodSourceInputs as EodSourceInputsData } from "@/types/eod";

export default function EodSourceInputs({ inputs }: { inputs: EodSourceInputsData }) {
  const notes: { label: string; value: string | undefined }[] = [
    { label: "Work notes", value: inputs.quick_notes },
    { label: "Next steps", value: inputs.next_steps },
    { label: "Learnings", value: inputs.learnings },
    { label: "Meetings", value: inputs.meetings },
    { label: "Metrics", value: inputs.metrics },
  ].filter((entry) => Boolean(entry.value));
  const entries = inputs.entries ?? [];
  const blockers = inputs.blockers ?? [];
  const dependencies = inputs.dependencies ?? [];
  if (!notes.length && !entries.length && !blockers.length && !dependencies.length) return null;

  return (
    <details className="rounded-lg border border-line bg-surface px-4 py-3">
      <summary className="cursor-pointer text-[13px] font-medium text-primary">View the inputs you recorded for this day</summary>
      <div className="mt-3 space-y-4 text-[13px]">
        {notes.map(({ label, value }) => (
          <section key={label}>
            <h3 className="font-medium text-text">{label}</h3>
            <p className="mt-1 whitespace-pre-wrap text-muted">{value}</p>
          </section>
        ))}
        {entries.length > 0 && (
          <section>
            <h3 className="font-medium text-text">Work entries</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
              {entries.map((entry, index) => {
                const details = [entry.time, entry.category, entry.status, entry.project].filter(Boolean).join(" · ");
                return (
                  <li key={`${entry.description}-${index}`}>
                    {entry.description}
                    {details && <span className="text-subtle"> ({details})</span>}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
        {blockers.length > 0 && (
          <section>
            <h3 className="font-medium text-text">Blockers</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
              {blockers.map((item, index) => (
                <li key={`${item.description}-${index}`}>
                  {item.description} ({[item.status, item.dependency, item.expected_resolution].filter(Boolean).join(" · ")})
                </li>
              ))}
            </ul>
          </section>
        )}
        {dependencies.length > 0 && (
          <section>
            <h3 className="font-medium text-text">Dependencies and asks</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
              {dependencies.map((item, index) => (
                <li key={`${item.description}-${index}`}>
                  {item.description} ({[item.type, item.owner, item.status].filter(Boolean).join(" · ")})
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </details>
  );
}
