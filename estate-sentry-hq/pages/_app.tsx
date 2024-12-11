// pages/_app.tsx
import type { AppProps, AppContext } from 'next/app';
// import { SWRConfig } from 'swr';
import dynamic from 'next/dynamic';
import '@/styles/globals.css';

// Dynamically import the client-side components with no SSR
const ClientProviders = dynamic(() => import('../components/ClientProviders'), {
    ssr: false,
});

function MyApp({ Component, pageProps }: AppProps) {
    return (
        <ClientProviders>
            <Component {...pageProps} />
        </ClientProviders>
    );
}

MyApp.getInitialProps = async (context: AppContext) => {
    let pageProps = {};

    if (context.Component.getInitialProps) {
        pageProps = await context.Component.getInitialProps(context.ctx);
    }

    return { pageProps };
};

export default MyApp;