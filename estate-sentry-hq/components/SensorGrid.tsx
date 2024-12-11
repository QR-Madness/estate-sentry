import { useEffect, useState } from 'react';
import useSWR from 'swr';
import { Sensor } from '@/types';

export const SensorGrid = () => {
    const [sensors, setSensors] = useState<Sensor[]>([]);

    const { data, error } = useSWR('/api/sensors', {
        refreshInterval: 1000,
    });

    useEffect(() => {
        const eventSource = new EventSource('/api/sensors/stream');

        eventSource.onmessage = (event) => {
            const sensorData = JSON.parse(event.data);
            setSensors(current => {
                const index = current.findIndex(s => s.id === sensorData.id);
                if (index === -1) return [...current, sensorData];
                const updated = [...current];
                updated[index] = sensorData;
                return updated;
            });
        };

        return () => {
            eventSource.close();
        };
    }, []);

    if (error) return <div>Error loading sensors</div>;
    if (!data) return <div>Loading...</div>;

    return (
        <div className="grid grid-cols-3 gap-4">
            {sensors.map((sensor) => (
                <div
                    key={sensor.id}
                    className={`p-4 rounded-lg ${
                        sensor.status === 'alert' ? 'bg-red-100' : 'bg-gray-100'
                    }`}
                >
                    <h3>{sensor.type}</h3>
                    <p>Value: {sensor.value}</p>
                    <p>Status: {sensor.status}</p>
                    <p>Last updated: {new Date(sensor.timestamp).toLocaleString()}</p>
                </div>
            ))}
        </div>
    );
};