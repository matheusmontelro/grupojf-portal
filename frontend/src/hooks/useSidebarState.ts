import { useState, useEffect } from 'react';

export const useSidebarState = () => {
  const [isOpen, setIsOpen] = useState(() => {
    const saved = localStorage.getItem('sidebarOpen');
    return saved !== null ? JSON.parse(saved) : true;
  });

  useEffect(() => {
    const handleToggle = (event: CustomEvent<{ isOpen: boolean }>) => {
      setIsOpen(event.detail.isOpen);
    };

    window.addEventListener('sidebarToggle', handleToggle as EventListener);
    return () => {
      window.removeEventListener('sidebarToggle', handleToggle as EventListener);
    };
  }, []);

  return {
    isOpen,
    sidebarWidth: isOpen ? 'w-64' : 'w-16',
    contentPadding: isOpen ? 'pl-64' : 'pl-16',
  };
};

export default useSidebarState;
