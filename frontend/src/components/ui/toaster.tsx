'use client';
import { useToast } from '@/hooks/use-toast';
import { Toast, ToastClose, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from '@radix-ui/react-toast';
import { cn } from '@/lib/utils';

export function Toaster() {
  const { toasts } = useToast();
  return (
    <ToastProvider>
      {toasts.map(({ id, title, description, ...props }) => (
        <Toast key={id} className={cn('group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border p-6 pr-8 shadow-lg transition-all bg-white border-gray-200')} {...props}>
          <div className="grid gap-1">
            {title && <ToastTitle className="text-sm font-semibold">{title}</ToastTitle>}
            {description && <ToastDescription className="text-sm opacity-90">{description}</ToastDescription>}
          </div>
          <ToastClose className="absolute right-2 top-2 rounded-md p-1 text-gray-500 opacity-0 transition-opacity hover:text-gray-900 focus:opacity-100 group-hover:opacity-100" />
        </Toast>
      ))}
      <ToastViewport className="fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]" />
    </ToastProvider>
  );
}
