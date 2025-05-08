import * as React from "react";
import Image from "next/image";

export function SetuLogo({ className = "", size = 40 }: { className?: string; size?: number }) {
  return (
    <Image
      src="/img.png"
      alt="Setu Logo"
      width={size}
      height={size}
      className={className}
      priority
    />
  );
} 