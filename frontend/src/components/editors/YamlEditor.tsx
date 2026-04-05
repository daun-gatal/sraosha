import { yaml } from '@codemirror/lang-yaml'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import CodeMirror from '@uiw/react-codemirror'
import { basicSetup } from '@uiw/codemirror-extensions-basic-setup'
import { useEffect, useMemo, useState } from 'react'

function useHtmlDarkClass(): boolean {
  const [dark, setDark] = useState(() =>
    typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : false,
  )

  useEffect(() => {
    const el = document.documentElement
    const sync = () => setDark(el.classList.contains('dark'))
    sync()
    const obs = new MutationObserver(sync)
    obs.observe(el, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])

  return dark
}

/** Light theme using app CSS variables (matches stone/zinc surfaces). */
const lightTheme = EditorView.theme(
  {
    '&': {
      backgroundColor: 'var(--color-surface-elevated)',
      color: 'var(--color-ink)',
    },
    '.cm-scroller': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    },
    '.cm-content': {
      caretColor: 'var(--color-ink)',
    },
    '.cm-gutters': {
      backgroundColor: 'var(--color-surface)',
      color: 'var(--color-ink-muted)',
      border: 'none',
      borderRight: '1px solid var(--color-border)',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'transparent',
    },
    '.cm-activeLine': {
      backgroundColor: 'oklch(0.55 0.14 195 / 0.08)',
    },
  },
  { dark: false },
)

export type YamlEditorProps = {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  placeholder?: string
  /** e.g. `20rem`, `28rem` */
  minHeight?: string
  className?: string
}

export function YamlEditor({
  value,
  onChange,
  disabled = false,
  placeholder,
  minHeight = '16rem',
  className,
}: YamlEditorProps) {
  const dark = useHtmlDarkClass()

  /** Use the wrapper's `theme` prop so `oneDark` is applied by @uiw/react-codemirror (avoids fighting defaultLightThemeOption #fff). In light mode, append `lightTheme` to override #fff with app CSS variables. */
  const extensions = useMemo(
    () => [
      yaml(),
      basicSetup({ tabSize: 2 }),
      EditorState.readOnly.of(disabled),
      ...(dark ? [] : [lightTheme]),
    ],
    [dark, disabled],
  )

  return (
    <div
      className={[
        'overflow-hidden rounded-xl border border-[var(--color-border)] dark:border-zinc-800',
        className ?? '',
      ]
        .join(' ')
        .trim()}
    >
      <CodeMirror
        value={value}
        onChange={onChange}
        theme={dark ? 'dark' : 'light'}
        extensions={extensions}
        editable={!disabled}
        readOnly={disabled}
        placeholder={placeholder}
        minHeight={minHeight}
        basicSetup={false}
        className="text-sm leading-relaxed [&_.cm-editor]:outline-none [&_.cm-focused]:outline-none"
        indentWithTab={false}
      />
    </div>
  )
}
