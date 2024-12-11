import { NextApiRequest, NextApiResponse } from 'next';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    const { id } = req.query;
    const sensorId = Array.isArray(id) ? id[0] : id;

    try {
        switch (req.method) {
            case 'GET':
                const sensor = await prisma.sensor.findUnique({
                    where: { id: sensorId },
                    include: {
                        lastReading: true,
                        alerts: {
                            where: { resolved: false },
                            orderBy: { timestamp: 'desc' },
                            take: 5
                        }
                    }
                });

                if (!sensor) {
                    return res.status(404).json({ message: 'Sensor not found' });
                }

                return res.status(200).json(sensor);

            case 'PUT':
                const updatedSensor = await prisma.sensor.update({
                    where: { id: sensorId },
                    data: {
                        ...req.body,
                        lastUpdate: new Date()
                    }
                });

                return res.status(200).json(updatedSensor);

            case 'DELETE':
                await prisma.sensor.delete({
                    where: { id: sensorId }
                });

                return res.status(204).end();

            default:
                res.setHeader('Allow', ['GET', 'PUT', 'DELETE']);
                return res.status(405).end(`Method ${req.method} Not Allowed`);
        }
    } catch (error) {
        console.error('API Error:', error);
        return res.status(500).json({ message: 'Internal Server Error' });
    } finally {
        await prisma.$disconnect();
    }
}