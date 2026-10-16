'use client';

import Link from 'next/link';
import { Activity, BarChart3, History, LayoutDashboard, Target, Wallet } from 'lucide-react';

const ITEMS = [
  { href: '/', label: 'Signalen', icon: LayoutDashboard },
  { href: '/portfolio', label: 'Portfolio', icon: Wallet },
  { href: '/history', label: 'Alert history', icon: History },
  { href: '/performance', label: 'Performance', icon: BarChart3 },
  { href: '/validation', label: 'Validatie', icon: Target },
];

export default function AppNav({ active, modelVersion = '6.2' }) {
  return (
    <aside className="ds-nav">
      <div className="ds-brand">
        <span className="ds-brandMark"><Activity size={16} strokeWidth={2.4} /></span>
        <span className="ds-brandName">MarketIntel</span>
      </div>
      <nav>
        {ITEMS.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={`ds-navItem${active === href ? ' is-active' : ''}`}>
            <Icon size={16} strokeWidth={2} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="ds-navFoot">
        <span>Model {modelVersion}</span>
        <span>Simulatie, geen financieel advies</span>
      </div>
    </aside>
  );
}
