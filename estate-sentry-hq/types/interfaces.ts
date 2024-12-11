export interface Sensor {
    id: string;
    type: string;
    value: number | boolean;
    timestamp: Date;
    status: 'active' | 'inactive' | 'alert';
}

export interface Alert {
    id: string;
    sensorId: string;
    type: string;
    severity: 'low' | 'medium' | 'high';
    timestamp: Date;
    resolved: boolean;
}