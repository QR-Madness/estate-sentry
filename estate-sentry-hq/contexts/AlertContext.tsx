import { createContext, useContext, useReducer, ReactNode } from 'react';

interface Alert {
    id: string;
    message: string;
    type: 'info' | 'warning' | 'error' | 'success';
    timestamp: Date;
}

interface AlertState {
    alerts: Alert[];
}

type AlertAction =
    | { type: 'ADD_ALERT'; payload: Alert }
    | { type: 'REMOVE_ALERT'; payload: string }
    | { type: 'CLEAR_ALERTS' };

const AlertContext = createContext<{
    state: AlertState;
    dispatch: React.Dispatch<AlertAction>;
} | undefined>(undefined);

const alertReducer = (state: AlertState, action: AlertAction): AlertState => {
    switch (action.type) {
        case 'ADD_ALERT':
            return {
                ...state,
                alerts: [...state.alerts, action.payload]
            };
        case 'REMOVE_ALERT':
            return {
                ...state,
                alerts: state.alerts.filter(alert => alert.id !== action.payload)
            };
        case 'CLEAR_ALERTS':
            return {
                ...state,
                alerts: []
            };
        default:
            return state;
    }
};

export const AlertProvider = ({ children }: { children: ReactNode }) => {
    const [state, dispatch] = useReducer(alertReducer, { alerts: [] });

    return (
        <AlertContext.Provider value={{ state, dispatch }}>
            {children}
        </AlertContext.Provider>
    );
};

export const useAlerts = () => {
    const context = useContext(AlertContext);
    if (context === undefined) {
        throw new Error('useAlerts must be used within an AlertProvider');
    }
    return context;
};