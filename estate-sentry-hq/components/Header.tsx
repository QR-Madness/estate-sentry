import { useState } from 'react';
import { useTheme } from 'next-themes';
import { useAuth } from '../contexts/AuthContext';
import { FiMenu, FiSun, FiMoon, FiBell, FiSettings } from 'react-icons/fi';

const Header = () => {
    const { theme, setTheme } = useTheme();
    const { user, logout } = useAuth();
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    return (
        <header className="bg-white dark:bg-gray-800 shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    <div className="flex">
                        <div className="flex-shrink-0 flex items-center">
                            <button
                                className="md:hidden p-2"
                                onClick={() => setIsMenuOpen(!isMenuOpen)}>
                                <FiMenu className={"h-6 w-6"} />
                            </button>
                            <span className="text-xl font-bold ml-2">Estate Sentry</span>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <button
                            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                            {theme === 'dark' ? <FiSun /> : <FiMoon />}
                        </button>

                        <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
                            <FiBell />
                        </button>

                        <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
                            <FiSettings />
                        </button>

                        {user ? (
                            <div className="relative">
                                <button
                                    className="flex items-center space-x-2"
                                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                                >
                                    <img
                                        src={user.avatar || '/default-avatar.png'}
                                        alt="User avatar"
                                        className="h-8 w-8 rounded-full"
                                    />
                                    <span>{user.name}</span>
                                </button>
                                {isMenuOpen && (
                                    <div className="absolute right-0 mt-2 w-48 rounded-md shadow-lg">
                                        <div className="rounded-md bg-white dark:bg-gray-800 shadow-xs">
                                            <div className="py-1">
                                                <button
                                                    onClick={logout}
                                                    className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 w-full text-left"
                                                >
                                                    Sign out
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg">
                                Sign in
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </header>
    );
};

export default Header;