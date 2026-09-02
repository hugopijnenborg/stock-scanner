import './globals.css';

export const metadata = {
  title: 'Stock Scanner',
  description: 'Data-driven stock opportunity scanner',
};

export default function RootLayout({ children }) {
  return <html lang="en"><head><link rel="stylesheet" href="/widget-fix.css" /></head><body>{children}</body></html>;
}
