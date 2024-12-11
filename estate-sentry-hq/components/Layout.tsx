import { ReactNode } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import AlertDisplay from './AlertDisplay';

interface LayoutProps {
    children: ReactNode;
}

const Layout = ({ children }: LayoutProps) => {
    return (
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
            <Header />
            <div className="flex">
                <Sidebar />
                <main className="flex-1 p-4">
                    <AlertDisplay />
                    {children}
                </main>
            </div>
        </div>
    );
};

export default Layout;