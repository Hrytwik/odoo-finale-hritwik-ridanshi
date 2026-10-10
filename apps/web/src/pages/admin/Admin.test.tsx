import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } }))
import { api } from '@/lib/api/client'
import { mockApi, renderPage } from '@/test/utils'
import FabricTypes from './FabricTypes'
import { Machines, Suppliers, Users, Workers } from './screens'

const post = vi.mocked(api.POST)
const patch = vi.mocked(api.PATCH)
const OWNER = { id: 1, username: 'owner', role: 'owner', display_name: 'Owner', worker_id: null, buyer_id: null }
const SUPERVISOR = { ...OWNER, role: 'supervisor' }

const SUPPLIERS = [
  { id: 1, name: 'Vardhman Yarns', phone: '98200 11111', lead_time_days: 10 },
  { id: 2, name: 'Arvind Mills', phone: null, lead_time_days: 5 },
]
const MACHINES = [
  { id: 1, code: 'LOOM-04', name: 'Loom 4', stage: 'weaving', rated_output_per_hour: 18, running_cost_per_hour: 220, active: true },
  { id: 2, code: 'SPIN-01', name: 'Ring frame 1', stage: 'spinning', rated_output_per_hour: 40, running_cost_per_hour: 150, active: false },
]
const WORKERS = [{ id: 5, code: 'W-05', name: 'Ravi Kumar', role: 'operator', daily_wage: 700, active: true }]
const YARNS = [
  { id: 1, code: 'COT-30', name: 'Cotton 30s', colour: 'white', reorder_level_kg: 500 },
  { id: 2, code: 'POLY-20', name: 'Polyester 20s', colour: 'white', reorder_level_kg: 300 },
]
const FABRICS = [
  { id: 1, name: 'Poplin 58in', width_in: 58, wastage_pct: 5, recipe: [{ yarn_type_id: 1, yarn_type_code: 'COT-30', kg_per_metre: 0.12 }] },
]
const BUYERS = [{ id: 1, name: 'Sharma Fabrics', contact_name: null, phone: null, email: null }]
const USERS = [{ id: 3, username: 'supervisor', role: 'supervisor', worker_id: 5, buyer_id: null }]

beforeEach(() => vi.clearAllMocks())

describe('Suppliers (a typical master list)', () => {
  it('lists each supplier with its phone and lead time', async () => {
    mockApi({ GET: { '/api/suppliers': SUPPLIERS } })
    renderPage(<Suppliers />)
    const row = (await screen.findByText('Vardhman Yarns')).closest('tr')!
    expect(row).toHaveTextContent('98200 11111')
    expect(row).toHaveTextContent('10 days')
  })

  it('shows an empty state with what to do', async () => {
    mockApi({ GET: { '/api/suppliers': [] } })
    renderPage(<Suppliers />)
    expect(await screen.findByText(/no suppliers yet/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add supplier/i })).toBeInTheDocument()
  })

  it('adds a supplier', async () => {
    mockApi({ GET: { '/api/suppliers': SUPPLIERS }, POST: { '/api/suppliers': SUPPLIERS[0] } })
    renderPage(<Suppliers />)
    await userEvent.click(await screen.findByRole('button', { name: /add supplier/i }))
    await userEvent.type(screen.getByLabelText('Name'), '  Reliance Yarns ')
    await userEvent.type(screen.getByLabelText('Phone'), '99999 00000')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add supplier' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/suppliers', { body: { name: 'Reliance Yarns', phone: '99999 00000', lead_time_days: 7 } })
  })

  it('asks for the name before sending anything', async () => {
    mockApi({ GET: { '/api/suppliers': SUPPLIERS } })
    renderPage(<Suppliers />)
    await userEvent.click(await screen.findByRole('button', { name: /add supplier/i }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add supplier' }))
    expect(await screen.findByText(/enter the name/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses a lead time that is not a number', async () => {
    mockApi({ GET: { '/api/suppliers': SUPPLIERS } })
    renderPage(<Suppliers />)
    await userEvent.click(await screen.findByRole('button', { name: /add supplier/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'X')
    const days = screen.getByLabelText(/lead time/i)
    await userEvent.clear(days)
    await userEvent.type(days, 'soon')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add supplier' }))
    expect(await screen.findByText(/enter a number/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('edits a supplier, starting from its current values', async () => {
    mockApi({ GET: { '/api/suppliers': SUPPLIERS }, PATCH: { '/api/suppliers/{item_id}': SUPPLIERS[0] } })
    renderPage(<Suppliers />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit supplier 1' }))
    const name = screen.getByLabelText('Name')
    expect(name).toHaveValue('Vardhman Yarns')
    await userEvent.clear(name)
    await userEvent.type(name, 'Vardhman Textiles')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await vi.waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch).toHaveBeenCalledWith('/api/suppliers/{item_id}', {
      params: { path: { item_id: 1 } },
      body: { name: 'Vardhman Textiles', phone: '98200 11111', lead_time_days: 10 },
    })
  })

  it("puts the server's reason under the field it is about", async () => {
    mockApi({
      GET: { '/api/suppliers': SUPPLIERS },
      POST: { '/api/suppliers': { status: 409, error: { code: 'CONFLICT', message: 'A supplier with this name exists', field: 'name', fields: null } } },
    })
    renderPage(<Suppliers />)
    await userEvent.click(await screen.findByRole('button', { name: /add supplier/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'Arvind Mills')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add supplier' }))
    expect(await screen.findByText('A supplier with this name exists')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows an unplaced server error in the dialog', async () => {
    mockApi({
      GET: { '/api/suppliers': SUPPLIERS },
      POST: { '/api/suppliers': { status: 500, error: { code: 'INTERNAL', message: 'The server had a problem', field: null, fields: null } } },
    })
    renderPage(<Suppliers />)
    await userEvent.click(await screen.findByRole('button', { name: /add supplier/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'New one')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add supplier' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The server had a problem')
  })
})

describe('Machines', () => {
  it('can choose the stage when adding, but not when editing', async () => {
    mockApi({ GET: { '/api/machines': MACHINES } })
    renderPage(<Machines />)
    await userEvent.click(await screen.findByRole('button', { name: /add machine/i }))
    expect(screen.getByLabelText('Stage')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Edit machine 1' }))
    expect(screen.queryByLabelText('Stage')).not.toBeInTheDocument()
  })

  it('adds a machine with its stage and rated output', async () => {
    mockApi({ GET: { '/api/machines': MACHINES }, POST: { '/api/machines': MACHINES[0] } })
    renderPage(<Machines />)
    await userEvent.click(await screen.findByRole('button', { name: /add machine/i }))
    await userEvent.type(screen.getByLabelText('Code'), 'LOOM-09')
    await userEvent.type(screen.getByLabelText('Name'), 'Loom 9')
    await userEvent.selectOptions(screen.getByLabelText('Stage'), 'weaving')
    await userEvent.type(screen.getByLabelText(/rated output/i), '18')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add machine' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/machines', {
      body: { code: 'LOOM-09', name: 'Loom 9', stage: 'weaving', rated_output_per_hour: 18, running_cost_per_hour: 0, active: true },
    })
  })

  it('marks machines that are out of use', async () => {
    mockApi({ GET: { '/api/machines': MACHINES } })
    renderPage(<Machines />)
    const row = (await screen.findByText('SPIN-01')).closest('tr')!
    expect(within(row).getByText('Inactive')).toBeInTheDocument()
  })
})

describe('Workers', () => {
  it('lets the owner add and edit', async () => {
    mockApi({ GET: { '/api/workers': WORKERS, '/api/auth/me': OWNER } })
    renderPage(<Workers />)
    expect(await screen.findByRole('button', { name: /add worker/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit worker 5' })).toBeInTheDocument()
  })

  it('lets a supervisor look but not change', async () => {
    mockApi({ GET: { '/api/workers': WORKERS, '/api/auth/me': SUPERVISOR } })
    renderPage(<Workers />)
    expect(await screen.findByText('Ravi Kumar')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /add worker/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /edit worker/i })).not.toBeInTheDocument()
  })
})

describe('Users', () => {
  it('shows who each login belongs to', async () => {
    mockApi({ GET: { '/api/users': USERS, '/api/workers': WORKERS, '/api/buyers': BUYERS } })
    renderPage(<Users />)
    const row = (await screen.findByText('supervisor', { selector: '.code-text' })).closest('tr')!
    await vi.waitFor(() => expect(row).toHaveTextContent('Ravi Kumar'))
  })

  it('creates a buyer login linked to a buyer', async () => {
    mockApi({ GET: { '/api/users': USERS, '/api/workers': WORKERS, '/api/buyers': BUYERS }, POST: { '/api/users': USERS[0] } })
    renderPage(<Users />)
    await userEvent.click(await screen.findByRole('button', { name: /add user/i }))
    await userEvent.type(screen.getByLabelText('Username'), 'sharma')
    await userEvent.selectOptions(screen.getByLabelText('Role'), 'buyer')
    await userEvent.type(screen.getByLabelText('Password'), 'secret123')
    await userEvent.selectOptions(await screen.findByLabelText('Linked buyer'), '1')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add user' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/users', { body: { username: 'sharma', password: 'secret123', role: 'buyer', worker_id: null, buyer_id: 1 } })
  })

  it('changes only the password and link when editing, and keeps the password if left empty', async () => {
    mockApi({ GET: { '/api/users': USERS, '/api/workers': WORKERS, '/api/buyers': BUYERS }, PATCH: { '/api/users/{item_id}': USERS[0] } })
    renderPage(<Users />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit user 3' }))
    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await vi.waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch).toHaveBeenCalledWith('/api/users/{item_id}', { params: { path: { item_id: 3 } }, body: { worker_id: 5 } })
  })
})

describe('Fabric types', () => {
  const setup = () => mockApi({ GET: { '/api/fabric-types': FABRICS, '/api/yarn-types': YARNS }, POST: { '/api/fabric-types': FABRICS[0] }, PATCH: { '/api/fabric-types/{item_id}': FABRICS[0] } })

  it('shows each fabric with its recipe', async () => {
    setup()
    renderPage(<FabricTypes />)
    const row = (await screen.findByText('Poplin 58in')).closest('tr')!
    expect(row).toHaveTextContent('58 in')
    expect(row).toHaveTextContent('COT-30 0.12 kg')
  })

  it('adds a fabric with two yarns in its recipe', async () => {
    setup()
    renderPage(<FabricTypes />)
    await userEvent.click(await screen.findByRole('button', { name: /add fabric type/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'Twill 60in')
    await userEvent.type(screen.getByLabelText(/width/i), '60')
    await userEvent.selectOptions(await screen.findByLabelText('Yarn 1'), '1')
    await userEvent.type(screen.getByLabelText('kg per metre for yarn 1'), '0.1')
    await userEvent.click(screen.getByRole('button', { name: /add a yarn/i }))
    await userEvent.selectOptions(screen.getByLabelText('Yarn 2'), '2')
    await userEvent.type(screen.getByLabelText('kg per metre for yarn 2'), '0.05')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add fabric type' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/api/fabric-types', {
      body: { name: 'Twill 60in', width_in: 60, wastage_pct: 5, recipe: [{ yarn_type_id: 1, kg_per_metre: 0.1 }, { yarn_type_id: 2, kg_per_metre: 0.05 }] },
    })
  })

  it('refuses the same yarn twice', async () => {
    setup()
    renderPage(<FabricTypes />)
    await userEvent.click(await screen.findByRole('button', { name: /add fabric type/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'X')
    await userEvent.type(screen.getByLabelText(/width/i), '40')
    await userEvent.selectOptions(await screen.findByLabelText('Yarn 1'), '1')
    await userEvent.type(screen.getByLabelText('kg per metre for yarn 1'), '0.1')
    await userEvent.click(screen.getByRole('button', { name: /add a yarn/i }))
    await userEvent.selectOptions(screen.getByLabelText('Yarn 2'), '1')
    await userEvent.type(screen.getByLabelText('kg per metre for yarn 2'), '0.1')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add fabric type' }))
    expect(await screen.findByText(/each yarn can appear only once/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('needs a yarn and an amount on every recipe line', async () => {
    setup()
    renderPage(<FabricTypes />)
    await userEvent.click(await screen.findByRole('button', { name: /add fabric type/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'X')
    await userEvent.type(screen.getByLabelText(/width/i), '40')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add fabric type' }))
    expect(await screen.findByText(/each line needs a yarn/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('removes a recipe line', async () => {
    setup()
    renderPage(<FabricTypes />)
    await userEvent.click(await screen.findByRole('button', { name: 'Edit fabric type Poplin 58in' }))
    await userEvent.click(screen.getByRole('button', { name: /add a yarn/i }))
    expect(screen.getByLabelText('Yarn 2')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove yarn 2' }))
    expect(screen.queryByLabelText('Yarn 2')).not.toBeInTheDocument()
    // the last remaining line cannot be removed
    expect(screen.queryByRole('button', { name: 'Remove yarn 1' })).not.toBeInTheDocument()
  })
})
