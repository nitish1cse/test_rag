import React from 'react';
import Image from 'next/image';

interface SetuLogoProps {
  size?: number;
  className?: string;
}

export function SetuLogo({ size = 40, className = "" }: SetuLogoProps) {
  return (
    <div className={`relative flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      <Image
        src="/img.png"
        alt="Setu Logo"
        width={size}
        height={size}
        className="object-contain"
        priority
        onError={(e) => {
          // If image fails to load, show a fallback text
          const target = e.target as HTMLImageElement;
          target.style.display = 'none';
          target.parentElement?.classList.add('bg-gray-100');
          if (target.parentElement) {
            target.parentElement.innerHTML = 'SETU';
          }
        }}
      />
    </div>
  );
} 