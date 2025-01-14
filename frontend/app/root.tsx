import {
  Links,
  Meta,
  Outlet,
  ScrollRestoration,
} from "@remix-run/react";

import "./css/wikipedia-base-20250101.css"; // https://meta.wikimedia.org/api/rest_v1/data/css/mobile/base
import "./css/wikipedia-site-20250101.css"; // https://ko.wikipedia.org/api/rest_v1/data/css/mobile/site
import "./css/wikipedia-pcs-20250101.css"; // https://meta.wikimedia.org/api/rest_v1/data/css/mobile/pcs

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
        
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-8RLS05GJ8G" />
        <script dangerouslySetInnerHTML={{
          __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-8RLS05GJ8G');
          `
        }} />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        {/* <Scripts /> */}
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}
