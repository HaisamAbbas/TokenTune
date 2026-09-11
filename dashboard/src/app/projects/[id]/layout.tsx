import { NavRail } from "@/components/nav-rail";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <NavRail projectId={id} />
      <div className="flex-1 flex flex-col min-w-0 bg-(--surface)">{children}</div>
    </div>
  );
}
