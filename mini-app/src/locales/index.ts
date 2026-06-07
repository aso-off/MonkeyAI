import testLocale from './test.json'
import ru from './ru.json'
import en from './en.json'
import de from './de.json'
import es from './es.json'
import fr from './fr.json'
import pl from './pl.json'
import pt from './pt.json'
import tr from './tr.json'

// test.json — эталон: все ключи, значения пустые.
// [] инферируется как never[] — расширяем до string[]
type _Raw = typeof testLocale
type LocaleSchema = { [K in keyof _Raw]: _Raw[K] extends readonly never[] ? string[] : _Raw[K] }

// Если в локали нет ключа из test.json — ошибка компиляции:
// Type '...' is missing the following properties from type 'LocaleSchema': key_name
export const messages = {
  ru: ru satisfies LocaleSchema,
  en: en satisfies LocaleSchema,
  de: de satisfies LocaleSchema,
  es: es satisfies LocaleSchema,
  fr: fr satisfies LocaleSchema,
  pl: pl satisfies LocaleSchema,
  pt: pt satisfies LocaleSchema,
  tr: tr satisfies LocaleSchema,
}

// loading_tips — массив, используется через tm(), не t()
type _StringKeys = { [K in keyof LocaleSchema as LocaleSchema[K] extends string ? K : never]: string }

declare module 'vue-i18n' {
  export interface DefineLocaleMessage extends _StringKeys {}
}
