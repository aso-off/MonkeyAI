import { describe, expect, it } from 'vitest'
import { renderMarkdown } from '@/utils/markdown'

const SAMPLES = [
  '```rust\nfn gcd(mut a: i64, mut b: i64) -> i64 {\n    a = a.abs();\n    b = b.abs();\n    a\n}\n```',
  'Use my_var and other_var together with some_long_name here.',
  'Bold **text**, italic _text_, code `inline_value` and a list:\n- one_item\n- two_item',
]

describe('renderMarkdown', () => {
  for (const md of SAMPLES) {
    it(`renders: ${md.slice(0, 28)}`, () => {
      const html = renderMarkdown(md)
      console.log('IN :', JSON.stringify(md))
      console.log('OUT:', html)
      expect(html).toBeTruthy()
    })
  }

  it('does not turn snake_case prose into italics', () => {
    const html = renderMarkdown('Use my_var and other_var here')
    expect(html).not.toContain('<em>')
  })

  it('keeps fenced code in a code block without emphasis', () => {
    const html = renderMarkdown('```rust\nlet x_y = a_b + c_d;\n```')
    expect(html).toContain('code-block')
    expect(html).not.toContain('<em>')
  })

  it('renders explicit italic outside code', () => {
    const html = renderMarkdown('this is _italic_ word')
    expect(html).toContain('<em>')
  })
})
