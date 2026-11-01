// Entirely fictional. Only used when the mod is opened with {demo:true}.
export function seedDemo(model) {
  model.reset({ base: "https://jira.example.test", projects: ["DEMO"], interval: 2, limit: 20, ttl: 10, context: "demo",
    fields: ["summary", "status", "assignee", "priority", "updated", "description", "comments"].map(id => ({ id })) });
  model.useSource("t-demo");
  model.merge(["DEMO-1042", "DEMO-1038", "DEMO-1026", "DEMO-1019"]);
  const issues = [
    ["DEMO-1042", "Keep filters when navigating back", "In Progress"],
    ["DEMO-1038", "Add an empty-results state", "In Review"],
    ["DEMO-1026", "Cache catalog thumbnails", "Done"],
    ["DEMO-1019", "Add keyboard navigation", "To Do"],
  ];
  for (const [key, summary, status] of issues) model.accept({
    key, summary, status,
    metadata: [{ id: "assignee", label: "Assignee", value: "Alex Example" }, { id: "priority", label: "Priority", value: "High" }, { id: "updated", label: "Updated", value: "31 Oct 2026" }],
    description: key === "DEMO-1042"
      ? "Returning from a product should restore catalog filters and the reading position.\n\nAcceptance criteria\n\n• Keep the selected category and price range.\n• Restore the previous scroll position.\n• Support browser Back and the catalog link."
      : "Make the fictional catalog easier to navigate.\n\n• Keep the active filters visible.\n• Support both keyboard and pointer navigation.",
    comments: [{ author: "Sam Sample", created: "2026-10-31T09:30:00Z", body: "Filter state now lives in the URL. Back navigation is covered by the regression checks." }],
  });
}
