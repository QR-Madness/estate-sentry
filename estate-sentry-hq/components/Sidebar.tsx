import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/router';
import {FiActivity, FiAlertCircle, FiCamera, FiHome, FiLayers, FiSettings, FiUsers} from 'react-icons/fi';

const menuItems = [
    {icon: FiHome, label: 'Dashboard', href: '/'},
    {icon: FiCamera, label: 'Cameras', href: '/cameras'},
    {icon: FiLayers, label: 'Sensors', href: '/sensors'},
    {icon: FiAlertCircle, label: 'Alerts', href: '/alerts'},
    {icon: FiActivity, label: 'Analytics', href: '/analytics'},
    {icon: FiUsers, label: 'Users', href: '/users'},
    {icon: FiSettings, label: 'Settings', href: '/settings'}
];

const Sidebar = () => {
    const router = useRouter();
    const [collapsed, setCollapsed] = useState(false);
    return (
        <aside className={` ${collapsed ? 'w-20' : 'w-64'}
        transition-all duration-300 ease-in-out min-h-screen bg-white dark:bg-gray-800 shadow-sm`}>
            <nav className="mt-5 px-2">
                <div className="space-y-1">
                    {menuItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = router.pathname === item.href;
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md ${isActive ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-200' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'}`}>
                                <Icon className={`${collapsed ? 'mr-0' : 'mr-3'}flex-shrink-0 h-6 w-6`}/>
                                {!collapsed && <span>{item.label}</span>}
                            </Link>
                        );
                    })}
                    <button onClick={() => setCollapsed(!collapsed)}>Collapse</button>
                </div>
            </nav>
        </aside>
    );
};

export default Sidebar;