import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { SshCredentials } from '@workspace/api-client-react';

interface AppState {
  apiKey: string;
  setApiKey: (key: string) => void;
  sshConfig: SshCredentials;
  setSshConfig: (config: SshCredentials) => void;
  adminMasterKey: string;
  setAdminMasterKey: (key: string) => void;
  logoutAdmin: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      apiKey: '',
      setApiKey: (key) => set({ apiKey: key }),
      sshConfig: {},
      setSshConfig: (config) => set({ sshConfig: config }),
      adminMasterKey: '',
      setAdminMasterKey: (key) => set({ adminMasterKey: key }),
      logoutAdmin: () => set({ adminMasterKey: '' }),
    }),
    {
      name: 'bruce-bera-store',
    }
  )
);
