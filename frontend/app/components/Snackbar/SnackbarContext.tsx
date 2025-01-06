"use client";

import React, { createContext, useContext, useCallback, useState } from 'react';
import { Toast } from 'flowbite-react';
import { HiCheck, HiX, HiExclamation, HiInformationCircle } from 'react-icons/hi';

type SnackbarType = 'success' | 'error' | 'warning' | 'info';

interface Snackbar {
  id: number;
  message: string;
  type: SnackbarType;
}

interface SnackbarContextType {
  addSnackbar: (message: string, type: SnackbarType) => void;
}

const SnackbarContext = createContext<SnackbarContextType | undefined>(undefined);

export const useSnackbar = () => {
  const context = useContext(SnackbarContext);
  if (!context) {
    throw new Error('useSnackbar must be used within a SnackbarProvider');
  }
  return context;
};

const getIcon = (type: SnackbarType) => {
  switch (type) {
    case 'success':
      return <HiCheck className="h-5 w-5" />;
    case 'error':
      return <HiX className="h-5 w-5" />;
    case 'warning':
      return <HiExclamation className="h-5 w-5" />;
    case 'info':
      return <HiInformationCircle className="h-5 w-5" />;
  }
};

const getIconColor = (type: SnackbarType) => {
  switch (type) {
    case 'success':
      return 'bg-green-100 text-green-500';
    case 'error':
      return 'bg-red-100 text-red-500';
    case 'warning':
      return 'bg-yellow-100 text-yellow-500';
    case 'info':
      return 'bg-blue-100 text-blue-500';
  }
};

export const SnackbarProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [snackbars, setSnackbars] = useState<Snackbar[]>([]);

  const addSnackbar = useCallback((message: string, type: SnackbarType) => {
    const id = Date.now();
    setSnackbars(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setSnackbars(prev => prev.filter(snackbar => snackbar.id !== id));
    }, 3000);
  }, []);

  const handleDismiss = (id: number) => {
    setSnackbars(prev => prev.filter(snackbar => snackbar.id !== id));
  };

  return (
    <SnackbarContext.Provider value={{ addSnackbar }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {snackbars.map(snackbar => (
          <Toast key={snackbar.id}>
            <div className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${getIconColor(snackbar.type)}`}>
              {getIcon(snackbar.type)}
            </div>
            <div className="ml-3 text-sm font-normal">
              {snackbar.message}
            </div>
            <Toast.Toggle onDismiss={() => handleDismiss(snackbar.id)} />
          </Toast>
        ))}
      </div>
    </SnackbarContext.Provider>
  );
}; 