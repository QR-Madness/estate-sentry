// components/ClientProviders.tsx
import { ReactNode } from 'react';
import { SWRConfig } from 'swr';
import { ThemeProvider } from 'next-themes';
import { AlertProvider } from '@/contexts/AlertContext';
import { AuthProvider } from '@/contexts/AuthContext';
import Layout from './Layout';

interface ClientProvidersProps {
    children: ReactNode;
}

const ClientProviders = ({ children }: ClientProvidersProps) => {
    return (
        <SWRConfig
            value={{
                fetcher: (url: string) => fetch(url).then((res) => res.json()),
                refreshInterval: 1000,
                revalidateOnFocus: true
            }}
        >
            <ThemeProvider attribute="class">
                <AuthProvider>
                    <AlertProvider>
                        <Layout>
                            {children}
                        </Layout>
                    </AlertProvider>
                </AuthProvider>
            </ThemeProvider>
        </SWRConfig>
    );
};

export default ClientProviders;