import { SensorGrid } from '@/components/SensorGrid';
// import { AlertPanel } from '@/components/AlertPanel';

export default function Home() {
    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-4">Estate Sentry Dashboard</h1>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div>
                    <h2 className="text-xl mb-2">Sensor Status</h2>
                    <SensorGrid />
                </div>
                <div>
                    <h2 className="text-xl mb-2">Active Alerts</h2>
                    {/*<AlertPanel />*/}
                </div>
            </div>
        </div>
    );
}