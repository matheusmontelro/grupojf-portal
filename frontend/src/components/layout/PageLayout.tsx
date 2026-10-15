import React from 'react';
import Sidebar from '../../pages/componentes/Sidebar.tsx';
import { useSidebarState } from '../../hooks/useSidebarState.ts';

interface PageLayoutProps {
  children: React.ReactNode;
}

export const PageLayout: React.FC<PageLayoutProps> = ({ children }) => {
  const { contentPadding } = useSidebarState();

  return (
    <div className="flex min-h-screen bg-[#f8f9fa]">
      <div className="flex-shrink-0 fixed h-full">
        <Sidebar />
      </div>
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-200 flex flex-col`}>
        {children}
      </div>
    </div>
  );
};

export default PageLayout;
