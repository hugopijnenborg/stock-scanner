import './globals.css';
import './ui/tokens.css';
import { SETTINGS_SCRIPT } from './ui/settings';
import './marketintel-overrides.css';
import './analyst-ui-hide.css';
import PortfolioBridge from './portfolio/PortfolioBridge';
import MeldingenWidget from './portfolio/MeldingenWidget';

export const metadata = {
  title: 'Stock Scanner',
  description: 'Data-driven stock opportunity scanner',
};

export default function RootLayout({ children }) {
  return <html lang="nl" data-theme="light" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: SETTINGS_SCRIPT }} /><link rel="stylesheet" href="/widget-fix.css" /><link rel="stylesheet" href="/readability.css" /></head><body><PortfolioBridge /><MeldingenWidget />{children}</body></html>;
}
