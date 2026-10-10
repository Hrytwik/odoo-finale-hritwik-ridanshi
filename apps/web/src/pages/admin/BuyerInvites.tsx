import { useQuery } from '@tanstack/react-query'
import { Copy } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { api, call } from '@/lib/api'

async function copy(text: string, what: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(`${what} copied`)
  } catch {
    toast.error('Could not copy. Select the text and copy it by hand.')
  }
}

/** For the owner: what to hand each buyer so they can create their own login. */
export default function BuyerInvites() {
  const invites = useQuery({ queryKey: ['master', 'buyer-invites'], queryFn: () => call(api.GET('/api/auth/buyer-invites')) })
  const signupLink = `${window.location.origin}/signup`
  return (
    <>
      <PageHeader
        eyebrow="Master data"
        title="Buyer invites"
        description="A buyer opens the sign-up link, types the email the mill holds for them and the invite code here, and their login is linked to their orders at once."
        actions={
          <Button variant="secondary" onClick={() => void copy(signupLink, 'Sign-up link')}>
            <Copy size={16} aria-hidden /> Copy the sign-up link
          </Button>
        }
      />
      <QueryBoundary query={invites}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title="No buyers yet" description="Add a buyer first, with an email, and their invite code appears here." />
          ) : (
            <Reveal>
              <Table>
                <thead>
                  <tr>
                    <th>Buyer</th>
                    <th>Email on record</th>
                    <th>Login</th>
                    <th>Invite code</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.buyer_id}>
                      <td>{r.buyer_name}</td>
                      <td>{r.email ?? <span className="muted">none</span>}</td>
                      <td>{r.has_account ? <Badge tone="green">Has a login</Badge> : <Badge tone="amber">Not signed up</Badge>}</td>
                      <td>
                        {r.invite_code ? (
                          <span className="row">
                            <span className="code-text">{r.invite_code}</span>
                            <Button variant="ghost" icon aria-label={`Copy the invite code for ${r.buyer_name}`} onClick={() => void copy(r.invite_code as string, 'Invite code')}>
                              <Copy size={16} aria-hidden />
                            </Button>
                          </span>
                        ) : (
                          <span className="muted text-sm">
                            Add an email in <Link to="/admin/buyers">Buyers</Link> first
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Reveal>
          )
        }
      </QueryBoundary>
    </>
  )
}
