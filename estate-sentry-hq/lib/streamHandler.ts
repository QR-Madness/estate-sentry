import type { SensorData } from '@/pages/api/sensors/stream';

export class StreamHandler {
    private buffer: Buffer;
    private expectedLength: number | null;

    constructor() {
        this.buffer = Buffer.alloc(0);
        this.expectedLength = null;
    }

    processData(chunk: Buffer): SensorData | null {
        // TODO ... rest of the implementation
        if (chunk === null) { // placeholder to satisfy ESLint
            return null;
        }
        return null;
    }

    private parseMessage(buffer: Buffer): SensorData {
        try {
            // First try to parse as JSON
            const jsonStr = buffer.toString('utf8');
            return JSON.parse(jsonStr) as SensorData;
        } catch {
            // If not JSON, handle as binary data
            return this.parseBinaryMessage(buffer);
        }
    }

    private parseBinaryMessage(buffer: Buffer): SensorData {
        const messageType = buffer[0];

        switch (messageType) {
            case 0x01: // Camera frame
                return {
                    id: buffer.slice(1, 17).toString('hex'),
                    type: 'camera',
                    value: buffer.slice(17).toString('base64'),
                    timestamp: new Date(),
                    status: 'active'
                };
            case 0x02: // Sensor data
                return {
                    id: buffer.slice(1, 17).toString('hex'),
                    type: 'motion',
                    value: buffer.readFloatBE(17),
                    timestamp: new Date(),
                    status: 'active'
                };
            default:
                throw new Error(`Unknown message type: ${messageType}`);
        }
    }
}