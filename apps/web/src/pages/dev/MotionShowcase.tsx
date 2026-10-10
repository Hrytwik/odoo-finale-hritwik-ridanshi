import { useState } from 'react'
import { KpiCard } from '@/components/common/KpiCard'
import { AnimatedBackground } from '@/components/motion/AnimatedBackground'
import { AnimatedGroup } from '@/components/motion/AnimatedGroup'
import { BorderTrail } from '@/components/motion/BorderTrail'
import { Disclosure } from '@/components/motion/Disclosure'
import { GlowEffect } from '@/components/motion/GlowEffect'
import { Magnetic } from '@/components/motion/Magnetic'
import { Spotlight } from '@/components/motion/Spotlight'
import { TextEffect } from '@/components/motion/TextEffect'
import { TextShimmer } from '@/components/motion/TextShimmer'
import { Tilt } from '@/components/motion/Tilt'
import { TransitionPanel } from '@/components/motion/TransitionPanel'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { formatKg, formatMoney } from '@/lib/format'

const TABS = ['Profit', 'Cash', 'Machines']

/** Dev-only: the animated pieces from motion-primitives, adapted to our plain CSS. */
export default function MotionShowcase() {
  const [tick, setTick] = useState(0)
  const [tab, setTab] = useState(0)
  const bump = () => setTick((t) => t + 1)

  return (
    <div className="stack">
      <Card title="Live numbers (tap the button to simulate a live update)">
        <div className="stack">
          <AnimatedGroup className="grid-cards">
            <Tilt>
              <KpiCard label="Invoiced this month" value={412000 + tick * 13750} format={formatMoney} hint="counts up" />
            </Tilt>
            <Tilt>
              <KpiCard label="Yarn free" value={Math.max(0, 1050 - tick * 87.5)} format={formatKg} hint="counts up" />
            </Tilt>
            <Tilt>
              <KpiCard label="Rolls in store" value={11 + tick} motion="odometer" hint="odometer digits" />
            </Tilt>
          </AnimatedGroup>
          <div>
            <Magnetic>
              <Button onClick={bump}>Simulate a live update</Button>
            </Magnetic>
          </div>
        </div>
      </Card>

      <div className="grid-cards">
        <div className="spotlight-host hero-demo">
          <Spotlight size={280} />
          <TextEffect as="h3" preset="fade-in-blur" per="word">
            Move the pointer over this card
          </TextEffect>
          <p className="muted text-sm">Spotlight follows the pointer; the heading reveals word by word.</p>
        </div>
        <div className="hero-demo" style={{ position: 'relative' }}>
          <GlowEffect blur={30} duration={9} style={{ opacity: 0.35, borderRadius: 16 }} />
          <div className="hero-demo-inner">
            <BorderTrail size={80} duration={6} />
            <h3>Glow and border trail</h3>
            <p className="muted text-sm">Use for one hero card per page.</p>
          </div>
        </div>
      </div>

      <Card title="Tabs with a sliding highlight and a transition panel">
        <div className="stack">
          <div className="pill-tabs">
            <AnimatedBackground defaultValue="Profit" onValueChange={(id) => id && setTab(TABS.indexOf(id))} className="pill-highlight">
              {TABS.map((t) => (
                <button key={t} type="button" data-id={t} className="pill-tab">
                  {t}
                </button>
              ))}
            </AnimatedBackground>
          </div>
          <TransitionPanel activeIndex={tab}>
            {[
              <p key="p">Profit panel: invoiced minus yarn, wages and machine running cost.</p>,
              <p key="c">Cash panel: received from buyers minus paid to suppliers and wages.</p>,
              <p key="m">Machines panel: running, idle and down hours per machine.</p>,
            ]}
          </TransitionPanel>
        </div>
      </Card>

      <Disclosure title="Lot ledger" meta="3 movements" defaultOpen>
        <Table>
          <thead>
            <tr>
              <th>When</th>
              <th>Kind</th>
              <th className="num">Kg</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>10 Oct, 9:30 am</td>
              <td>Receipt</td>
              <td className="num">800</td>
            </tr>
            <tr>
              <td>10 Oct, 11:30 am</td>
              <td>Issue to SPIN-01</td>
              <td className="num">-587.5</td>
            </tr>
            <tr>
              <td>10 Oct, 4:00 pm</td>
              <td>Return</td>
              <td className="num">12.5</td>
            </tr>
          </tbody>
        </Table>
      </Disclosure>

      <Card>
        <TextShimmer>The assistant is looking at your orders…</TextShimmer>
      </Card>
    </div>
  )
}
