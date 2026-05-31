import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export function ButtonLink({
  href,
  children,
  className
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex h-9 items-center rounded-md border bg-card px-3 text-sm font-medium hover:bg-muted",
        className
      )}
    >
      {children}
    </Link>
  );
}
