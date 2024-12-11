import { NextApiRequest, NextApiResponse } from 'next';
import { SensorRelay } from '@/lib/sensorRelay';

// Define specific types for your sensor data
interface SensorData {
    id: string;
    type: 'motion' | 'camera' | 'temperature' | 'humidity' | 'door' | 'window';
    value: number | boolean | string;
    timestamp: Date;
    status: 'active' | 'inactive' | 'alert';
    location?: string;
    metadata?: Record<string, unknown>;
}

interface SensorStreamData {
    event: 'update' | 'alert' | 'status';
    data: SensorData;
}

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'GET') {
        return res.status(405).json({ message: 'Method not allowed' });
    }

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const sensorRelay = new SensorRelay();

    const sendData = (data: SensorStreamData) => {
        res.write(`data: ${JSON.stringify(data)}\n\n`);
    };

    sensorRelay.on('sensorUpdate', (data: SensorData) => {
        sendData({
            event: 'update',
            data
        });
    });

    // Handle client disconnect
    req.on('close', () => {
        sensorRelay.removeAllListeners('sensorUpdate');
    });

    // Start relay server
    sensorRelay.start();
}

// If you need to export the types for use in other files
export type { SensorData, SensorStreamData };