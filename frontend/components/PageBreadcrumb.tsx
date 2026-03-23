"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

const ROUTE_LABELS: Record<string, string> = {
  chat: "Chat",
  collections: "Collections",
  documents: "Documents",
  settings: "Settings",
  observability: "Observability",
};

interface BreadcrumbItemDef {
  label: string;
  href?: string;
}

interface PageBreadcrumbProps {
  items?: BreadcrumbItemDef[];
}

export default function PageBreadcrumb({ items }: PageBreadcrumbProps) {
  const pathname = usePathname();

  const crumbs: BreadcrumbItemDef[] = items ?? deriveCrumbs(pathname);

  if (crumbs.length === 0) return null;

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1;
          return (
            <BreadcrumbItem key={crumb.label}>
              {idx > 0 && <BreadcrumbSeparator />}
              {isLast || !crumb.href ? (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              ) : (
                <BreadcrumbLink render={<Link href={crumb.href} />}>
                  {crumb.label}
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

function deriveCrumbs(pathname: string): BreadcrumbItemDef[] {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return [];

  const result: BreadcrumbItemDef[] = [];
  let path = "";

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    path += `/${seg}`;
    const label = ROUTE_LABELS[seg] ?? seg;

    if (i < segments.length - 1) {
      result.push({ label, href: path });
    } else {
      result.push({ label });
    }
  }

  return result;
}
