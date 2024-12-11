import { EventEmitter } from 'events';
import type { SensorData } from '../pages/api/sensors/stream';

export class SensorRelay extends EventEmitter {
    private sensorData: Map<string, SensorData>;

    constructor() {
        super();
        this.sensorData = new Map();
    }

    public start(port: number = 3001): void {
        // TODO Implementation
        if (port === null) { //placeholder to satisfy eslint for now
            return;
        }
    }

    private handleIncomingData(data: Buffer | string): void {
        try {
            let parsedData: SensorData;

            if (typeof data === 'string') {
                parsedData = JSON.parse(data) as SensorData;
            } else {
                // Handle binary data conversion to SensorData
                parsedData = this.parseBinaryData(data);
            }

            this.updateSensorData(parsedData);
            this.emit('sensorUpdate', parsedData);
        } catch (error) {
            console.error('Error processing incoming data:', error);
        }
    }

    private parseBinaryData(data: Buffer): SensorData {
        // Implement your binary data parsing logic here
        // This is just an example structure
        return {
            id: data.slice(0, 16).toString('hex'),
            type: 'motion', // You'll need to determine this from your binary format
            value: data.readFloatBE(16),
            timestamp: new Date(),
            status: 'active'
        };
    }

    private updateSensorData(data: SensorData): void {
        this.sensorData.set(data.id, {
            ...data,
            timestamp: new Date()
        });
    }

    public getSensorData(id: string): SensorData | undefined {
        return this.sensorData.get(id);
    }

    public getAllSensorData(): SensorData[] {
        return Array.from(this.sensorData.values());
    }
}