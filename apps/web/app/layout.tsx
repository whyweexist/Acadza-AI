import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Acadza Review · Faculty Workspace', description: 'Evidence-first question quality review' };
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
