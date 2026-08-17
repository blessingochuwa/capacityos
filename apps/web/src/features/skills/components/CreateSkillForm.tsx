import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useCreateSkill } from '../hooks/useSkillMutations'

export function CreateSkillForm() {
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const createSkill = useCreateSkill()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    createSkill.mutate(
      { name: name.trim(), category: category.trim() || undefined },
      {
        onSuccess: () => {
          setName('')
          setCategory('')
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="new-skill-name" className="text-xs font-medium text-slate-400">
          New skill name
        </label>
        <input
          id="new-skill-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Backend Development"
          className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="new-skill-category" className="text-xs font-medium text-slate-400">
          Category (optional)
        </label>
        <input
          id="new-skill-category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          placeholder="e.g. Engineering"
          className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>
      <Button type="submit" variant="primary" disabled={!name.trim() || createSkill.isPending}>
        {createSkill.isPending ? 'Adding…' : 'Add skill'}
      </Button>
      {createSkill.isError ? (
        <p role="alert" className="text-xs text-rose-300">
          {createSkill.error.message}
        </p>
      ) : null}
    </form>
  )
}
