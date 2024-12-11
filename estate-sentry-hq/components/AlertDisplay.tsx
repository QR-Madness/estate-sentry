import { useEffect } from 'react';
import { useAlerts } from '@/contexts/AlertContext';
import { FiX, FiInfo, FiAlertCircle, FiCheckCircle } from 'react-icons/fi';

const AlertDisplay = () => {
    const { state, dispatch } = useAlerts();

    const getAlertIcon = (type: string) => {
        switch (type) {
            case 'info':
                return <FiInfo className="h-5 w-5 text-blue-400" />;
            case 'warning':
                return <FiAlertCircle className="h-5 w-5 text-yellow-400" />;
            case 'error':
                return <FiAlertCircle className="h-5 w-5 text-red-400" />;
            case 'success':
                return <FiCheckCircle className="h-5 w-5 text-green-400" />;
            default:
                return null;
        }
    };

    useEffect(() => {
        // Auto-remove alerts after 5 seconds
        const timeouts = state.alerts.map(alert => {
            return setTimeout(() => {
                dispatch({ type: 'REMOVE_ALERT', payload: alert.id });
            }, 5000);
        });

        return () => {
            timeouts.forEach(timeout => clearTimeout(timeout));
        };
    }, [state.alerts, dispatch]);

    return (
        <div className="fixed top-4 right-4 z-50 space-y-2">
            {state.alerts.map(alert => (
                <div
                    key={alert.id}
                    className={`
            flex items-center p-4 rounded-lg shadow-lg
            ${
                        alert.type === 'error'
                            ? 'bg-red-50 dark:bg-red-900'
                            : alert.type === 'warning'
                                ? 'bg-yellow-50 dark:bg-yellow-900'
                                : alert.type === 'success'
                                    ? 'bg-green-50 dark:bg-green-900'
                                    : 'bg-blue-50 dark:bg-blue-900'
                    }
          `}
                >
                    <div className="flex-shrink-0">
                        {getAlertIcon(alert.type)}
                    </div>
                    <div className="ml-3">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            {alert.message}
                        </p>
                    </div>
                    <div className="ml-4">
                        <button
                            className="inline-flex text-gray-400 hover:text-gray-500 focus:outline-none"
                            onClick={() => dispatch({ type: 'REMOVE_ALERT', payload: alert.id })}
                        >
                            <FiX className="h-5 w-5" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default AlertDisplay;