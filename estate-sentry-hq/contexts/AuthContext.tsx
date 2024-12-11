import {
    createContext,
    useContext,
    useState,
    useEffect,
    ReactNode
} from 'react';
import { useRouter } from 'next/router';

interface User {
    id: string;
    name: string;
    email: string;
    avatar?: string;
    role: 'admin' | 'user';
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    register: (data: RegisterData) => Promise<void>;
}

interface RegisterData {
    name: string;
    email: string;
    password: string;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        // Check for stored auth token and validate it
        const checkAuth = async () => {
            try {
                const token = localStorage.getItem('auth_token');
                if (token) {
                    // Validate token with your backend
                    const response = await fetch('/api/auth/validate', {
                        headers: {
                            Authorization: `Bearer ${token}`
                        }
                    });

                    if (response.ok) {
                        const userData = await response.json();
                        setUser(userData);
                    } else {
                        localStorage.removeItem('auth_token');
                    }
                }
            } catch (error) {
                console.error('Auth validation error:', error);
            } finally {
                setLoading(false);
            }
        };

        checkAuth();
    }, []);

    const login = async (email: string, password: string) => {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            if (!response.ok) throw new Error('Login failed');

            const { token, user: userData } = await response.json();
            localStorage.setItem('auth_token', token);
            setUser(userData);
            router.push('/');
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    };

    const logout = async () => {
        try {
            await fetch('/api/auth/logout', { method: 'POST' });
            localStorage.removeItem('auth_token');
            setUser(null);
            router.push('/login');
        } catch (error) {
            console.error('Logout error:', error);
        }
    };

    const register = async (data: RegisterData) => {
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) throw new Error('Registration failed');

            const { token, user: userData } = await response.json();
            localStorage.setItem('auth_token', token);
            setUser(userData);
            router.push('/');
        } catch (error) {
            console.error('Registration error:', error);
            throw error;
        }
    };

    return (
        <AuthContext.Provider
            value={{ user, loading, login, logout, register }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};