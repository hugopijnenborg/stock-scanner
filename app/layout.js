import './globals.css';
import './marketintel-overrides.css';
import PortfolioBridge from './portfolio/PortfolioBridge';
import PortfolioTradePlan from './portfolio/PortfolioTradePlan';

export const metadata = {
  title: 'Stock Scanner',
  description: 'Data-driven stock opportunity scanner',
};

export default function RootLayout({ children }) {
  return <html lang="en"><head><link rel="stylesheet" href="/widget-fix.css" /><link rel="stylesheet" href="/readability.css" /></head><body><PortfolioBridge /><PortfolioTradePlan />{children}</body></html>;
}
