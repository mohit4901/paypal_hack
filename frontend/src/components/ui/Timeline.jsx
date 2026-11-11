import React from 'react';

export default function Timeline({ children, className = '' }) {
  return (
    <div className={`relative space-y-0 ${className}`}>
      {children}
    </div>
  );
}

