import React, { CSSProperties, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Eye, Printer } from 'lucide-react';
import {
  AnamneseConsultaItem,
  AnamneseStatus,
} from '../../api/anamneseDigital.ts';

interface AnamneseActionsModalProps {
  isOpen: boolean;
  item: AnamneseConsultaItem | null;
  anchorElement: HTMLElement | null;
  onClose: () => void;
  onView: () => void;
  onPrint: () => void;
}

const MENU_GAP = 8;
const VIEWPORT_PADDING = 12;

const AnamneseActionsModal: React.FC<AnamneseActionsModalProps> = ({
  isOpen,
  item,
  anchorElement,
  onClose,
  onView,
  onPrint,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const firstActionRef = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<CSSProperties | null>(null);
  const canPrint = item?.status === AnamneseStatus.ASSINADO || item?.status === AnamneseStatus.EXPIRADO;

  const updatePosition = useCallback(() => {
    if (!anchorElement || !menuRef.current) return;

    const anchorRect = anchorElement.getBoundingClientRect();
    const menuRect = menuRef.current.getBoundingClientRect();
    const availableWidth = Math.max(0, window.innerWidth - VIEWPORT_PADDING * 2);
    const width = Math.min(menuRect.width || 224, availableWidth);
    const maxLeft = Math.max(VIEWPORT_PADDING, window.innerWidth - width - VIEWPORT_PADDING);
    const left = Math.min(Math.max(VIEWPORT_PADDING, anchorRect.right - width), maxLeft);
    const spaceBelow = window.innerHeight - anchorRect.bottom;
    const opensBelow = spaceBelow >= menuRect.height + MENU_GAP || spaceBelow >= anchorRect.top;
    const preferredTop = opensBelow
      ? anchorRect.bottom + MENU_GAP
      : anchorRect.top - menuRect.height - MENU_GAP;
    const maxTop = Math.max(VIEWPORT_PADDING, window.innerHeight - menuRect.height - VIEWPORT_PADDING);
    const top = Math.min(Math.max(VIEWPORT_PADDING, preferredTop), maxTop);

    setPosition({ left, top, width });
  }, [anchorElement]);

  useLayoutEffect(() => {
    if (!isOpen || !anchorElement) {
      setPosition(null);
      return;
    }

    updatePosition();
    window.requestAnimationFrame(() => {
      updatePosition();
      firstActionRef.current?.focus();
    });
  }, [anchorElement, isOpen, updatePosition]);

  useEffect(() => {
    if (!isOpen || !anchorElement) return undefined;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || anchorElement.contains(target)) return;
      onClose();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }

      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) || !menuRef.current) return;
      const actions = Array.from(menuRef.current.querySelectorAll<HTMLButtonElement>('button:not([disabled])'));
      if (actions.length === 0) return;

      event.preventDefault();
      const currentIndex = actions.indexOf(document.activeElement as HTMLButtonElement);
      if (event.key === 'Home') actions[0].focus();
      else if (event.key === 'End') actions[actions.length - 1].focus();
      else if (event.key === 'ArrowDown') actions[(currentIndex + 1 + actions.length) % actions.length].focus();
      else actions[(currentIndex - 1 + actions.length) % actions.length].focus();
    };

    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
      anchorElement.focus();
    };
  }, [anchorElement, isOpen, onClose, updatePosition]);

  if (!isOpen || !item || !anchorElement) return null;

  return (
    <div
      ref={menuRef}
      id="anamnese-actions-menu"
      role="menu"
      aria-label={`Ações da anamnese de ${item.beneficiario_nome}`}
      style={position || { left: VIEWPORT_PADDING, top: VIEWPORT_PADDING, visibility: 'hidden' }}
      className="fixed z-[100010] w-56 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-xl border border-[#e5e7eb] bg-white p-1.5 shadow-xl"
    >
      <button
        ref={firstActionRef}
        type="button"
        role="menuitem"
        onClick={onView}
        className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-medium text-[#1a1a1a] hover:bg-gray-100 focus:bg-gray-100 focus:outline-none"
      >
        <Eye className="h-4 w-4 text-[#6b7280]" />
        Visualizar anamnese
      </button>
      <button
        type="button"
        role="menuitem"
        onClick={() => {
          onPrint();
          onClose();
        }}
        disabled={!canPrint}
        title={canPrint ? 'Abrir PDF para impressão' : 'Disponível após a assinatura'}
        className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-medium text-[#1a1a1a] hover:bg-gray-100 focus:bg-gray-100 focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Printer className="h-4 w-4 text-[#6b7280]" />
        Imprimir anamnese
      </button>
    </div>
  );
};

export default AnamneseActionsModal;
