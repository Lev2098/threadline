import { computed, ref } from 'vue'

export type Locale = 'uk' | 'ru'

const uk = {
  appName: 'Threadline',
  heroTitle: 'Говоримо по суті.',
  heroLead: 'Відповідайте на будь-який коментар — гілки ростуть скільки завгодно глибоко, а нові повідомлення з’являються наживо.',
  statThreads: 'обговорень',
  startDiscussion: 'Почати обговорення',
  live: 'наживо',
  offline: 'офлайн',
  newComments: (n: number) => `${n} ${plural(n, 'новий коментар', 'нові коментарі', 'нових коментарів')} — показати`,
  colAuthor: 'Автор',
  colComment: 'Коментар',
  colEmail: 'E-mail',
  colDate: 'Дата',
  colReplies: 'Відповіді',
  sortBy: (col: string) => `Сортувати: ${col}`,
  empty: 'Ще жодного обговорення. Напишіть перше — інші побачать його одразу.',
  loading: 'Завантаження…',
  loadError: 'Не вдалося завантажити коментарі. Перевірте з’єднання та спробуйте ще раз.',
  retry: 'Спробувати ще раз',
  reply: 'Відповісти',
  replies: (n: number) => `${n} ${plural(n, 'відповідь', 'відповіді', 'відповідей')}`,
  showThread: 'Показати гілку',
  hideThread: 'Згорнути гілку',
  loadMoreReplies: 'Завантажити ще відповіді',
  noReplies: 'Відповідей поки немає.',
  page: 'Сторінка',
  prev: 'Назад',
  next: 'Далі',
  search: 'Пошук',
  searchPlaceholder: 'Пошук у коментарях…',
  searchResults: (n: number, q: string) =>
    n >= SEARCH_CAP ? `${formatCount(n)}+ результатів за «${q}»` : `${formatCount(n)} ${plural(n, 'результат', 'результати', 'результатів')} за «${q}»`,
  searchFailed: 'Пошук тимчасово недоступний. Спробуйте ще раз за хвилину.',
  searchNothing: (q: string) => `За запитом «${q}» нічого не знайдено. Спробуйте інше слово.`,
  closeSearch: 'Закрити пошук',
  composerNew: 'Нове обговорення',
  composerReply: (name: string) => `Відповідь для ${name}`,
  fieldUsername: 'Ім’я користувача',
  fieldUsernameHint: 'Латинські літери та цифри',
  fieldEmail: 'E-mail',
  fieldHomepage: 'Домашня сторінка',
  optional: 'необов’язково',
  fieldText: 'Повідомлення',
  fieldTextHint: 'Дозволені теги: <a>, <i>, <strong>, <code>',
  write: 'Написати',
  preview: 'Перегляд',
  previewEmpty: 'Тут з’явиться повідомлення в тому вигляді, в якому його побачать інші.',
  attach: 'Додати файл',
  attachHint: 'JPG, GIF, PNG (зменшимо до 320×240) або TXT до 100 КБ',
  removeFile: 'Прибрати файл',
  captcha: 'Символи з картинки',
  captchaRefresh: 'Інша картинка',
  submit: 'Опублікувати',
  submitting: 'Публікуємо…',
  cancel: 'Скасувати',
  close: 'Закрити',
  published: 'Опубліковано',
  linkPrompt: 'Адреса посилання (https://…)',
  fixFields: 'Виправте виділені поля.',
  theme: 'Змінити тему',
  language: 'Мова',
  errUsername: 'Лише латинські літери та цифри.',
  errRequired: 'Обов’язкове поле.',
  errEmail: 'Введіть коректний e-mail.',
  errUrl: 'Адреса має починатися з http:// або https://',
  errFileType: 'Підтримуються лише JPG, GIF, PNG або TXT.',
  errFileTxt: 'Текстовий файл має бути не більше 100 КБ.',
  errTag: (tag: string) => `Тег <${tag}> не дозволений.`,
  errUnclosed: (tag: string) => `Тег <${tag}> не закрито.`,
  errMismatch: (exp: string, got: string) => `Очікувався </${exp}>, а знайдено </${got}>.`,
  errOrphan: (tag: string) => `Закривальний </${tag}> без відкривального.`,
  errHref: 'У посиланні потрібен href з http://, https:// або mailto:',
  quoteLabel: 'Цитата з попереднього коментаря',
  openFile: 'Відкрити файл',
  homepage: 'Домашня сторінка автора',
  captchaLoadError: 'Не вдалося завантажити картинку. Натисніть «Інша картинка».',
  errCaptcha: 'Символи не збігаються. Введіть символи з нової картинки.',
  errAttachment: 'Файл пошкоджений або не є зображенням JPG, GIF чи PNG.',
  errFileTooBig: 'Файл завеликий: зображення до 10 МБ, текст до 100 КБ.',
  errParent: 'Коментар, на який ви відповідаєте, недоступний.',
  errRateLimit: 'Забагато запитів. Зачекайте кілька секунд і спробуйте ще раз.',
  errServer: 'Сервер тимчасово недоступний. Спробуйте ще раз за хвилину.',
  errPublish: 'Не вдалося опублікувати. Перевірте з’єднання та спробуйте ще раз.',
  errLinkUrl: 'Адреса має починатися з https://, http:// або mailto:',
  insertLink: 'Вставити',
  kb: 'КБ',
  captchaAlt: 'Картинка з символами',
  formatting: 'Форматування',
  download: 'Завантажити файл',
}

type Dict = typeof uk

const ru: Dict = {
  appName: 'Threadline',
  heroTitle: 'Говорим по делу.',
  heroLead: 'Отвечайте на любой комментарий — ветки растут сколько угодно глубоко, а новые сообщения появляются вживую.',
  statThreads: 'обсуждений',
  startDiscussion: 'Начать обсуждение',
  live: 'вживую',
  offline: 'офлайн',
  newComments: (n: number) => `${n} ${plural(n, 'новый комментарий', 'новых комментария', 'новых комментариев')} — показать`,
  colAuthor: 'Автор',
  colComment: 'Комментарий',
  colEmail: 'E-mail',
  colDate: 'Дата',
  colReplies: 'Ответы',
  sortBy: (col: string) => `Сортировать: ${col}`,
  empty: 'Пока ни одного обсуждения. Напишите первое — другие увидят его сразу.',
  loading: 'Загрузка…',
  loadError: 'Не удалось загрузить комментарии. Проверьте соединение и попробуйте снова.',
  retry: 'Попробовать снова',
  reply: 'Ответить',
  replies: (n: number) => `${n} ${plural(n, 'ответ', 'ответа', 'ответов')}`,
  showThread: 'Показать ветку',
  hideThread: 'Свернуть ветку',
  loadMoreReplies: 'Загрузить ещё ответы',
  noReplies: 'Ответов пока нет.',
  page: 'Страница',
  prev: 'Назад',
  next: 'Далее',
  search: 'Поиск',
  searchPlaceholder: 'Поиск по комментариям…',
  searchResults: (n: number, q: string) =>
    n >= SEARCH_CAP ? `${formatCount(n)}+ результатов по «${q}»` : `${formatCount(n)} ${plural(n, 'результат', 'результата', 'результатов')} по «${q}»`,
  searchFailed: 'Поиск временно недоступен. Попробуйте ещё раз через минуту.',
  searchNothing: (q: string) => `По запросу «${q}» ничего не найдено. Попробуйте другое слово.`,
  closeSearch: 'Закрыть поиск',
  composerNew: 'Новое обсуждение',
  composerReply: (name: string) => `Ответ для ${name}`,
  fieldUsername: 'Имя пользователя',
  fieldUsernameHint: 'Латинские буквы и цифры',
  fieldEmail: 'E-mail',
  fieldHomepage: 'Домашняя страница',
  optional: 'необязательно',
  fieldText: 'Сообщение',
  fieldTextHint: 'Разрешённые теги: <a>, <i>, <strong>, <code>',
  write: 'Написать',
  preview: 'Просмотр',
  previewEmpty: 'Здесь появится сообщение в том виде, в каком его увидят другие.',
  attach: 'Добавить файл',
  attachHint: 'JPG, GIF, PNG (уменьшим до 320×240) или TXT до 100 КБ',
  removeFile: 'Убрать файл',
  captcha: 'Символы с картинки',
  captchaRefresh: 'Другая картинка',
  submit: 'Опубликовать',
  submitting: 'Публикуем…',
  cancel: 'Отмена',
  close: 'Закрыть',
  published: 'Опубликовано',
  linkPrompt: 'Адрес ссылки (https://…)',
  fixFields: 'Исправьте выделенные поля.',
  theme: 'Сменить тему',
  language: 'Язык',
  errUsername: 'Только латинские буквы и цифры.',
  errRequired: 'Обязательное поле.',
  errEmail: 'Введите корректный e-mail.',
  errUrl: 'Адрес должен начинаться с http:// или https://',
  errFileType: 'Поддерживаются только JPG, GIF, PNG или TXT.',
  errFileTxt: 'Текстовый файл должен быть не больше 100 КБ.',
  errTag: (tag: string) => `Тег <${tag}> не разрешён.`,
  errUnclosed: (tag: string) => `Тег <${tag}> не закрыт.`,
  errMismatch: (exp: string, got: string) => `Ожидался </${exp}>, а найден </${got}>.`,
  errOrphan: (tag: string) => `Закрывающий </${tag}> без открывающего.`,
  errHref: 'В ссылке нужен href с http://, https:// или mailto:',
  quoteLabel: 'Цитата из предыдущего комментария',
  openFile: 'Открыть файл',
  homepage: 'Домашняя страница автора',
  captchaLoadError: 'Не удалось загрузить картинку. Нажмите «Другая картинка».',
  errCaptcha: 'Символы не совпадают. Введите символы с новой картинки.',
  errAttachment: 'Файл повреждён или не является изображением JPG, GIF или PNG.',
  errFileTooBig: 'Файл слишком большой: изображение до 10 МБ, текст до 100 КБ.',
  errParent: 'Комментарий, на который вы отвечаете, недоступен.',
  errRateLimit: 'Слишком много запросов. Подождите несколько секунд и попробуйте снова.',
  errServer: 'Сервер временно недоступен. Попробуйте ещё раз через минуту.',
  errPublish: 'Не удалось опубликовать. Проверьте соединение и попробуйте снова.',
  errLinkUrl: 'Адрес должен начинаться с https://, http:// или mailto:',
  insertLink: 'Вставить',
  kb: 'КБ',
  captchaAlt: 'Картинка с символами',
  formatting: 'Форматирование',
  download: 'Скачать файл',
}

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

function initialLocale(): Locale {
  try {
    const saved = localStorage.getItem('threadline.locale')
    if (saved === 'uk' || saved === 'ru') return saved
  } catch {
    /* storage unavailable */
  }
  return navigator.language.toLowerCase().startsWith('ru') ? 'ru' : 'uk'
}

export const locale = ref<Locale>(initialLocale())
const dictionaries: Record<Locale, Dict> = { uk, ru }
export const t = computed(() => dictionaries[locale.value])

export function setLocale(next: Locale): void {
  locale.value = next
  document.documentElement.lang = next
  try {
    localStorage.setItem('threadline.locale', next)
  } catch {
    /* ignore */
  }
}

/** Elasticsearch counts hits exactly only up to this number. */
const SEARCH_CAP = 10_000

export function formatCount(n: number): string {
  return n.toLocaleString(locale.value === 'uk' ? 'uk-UA' : 'ru-RU')
}

const formatters = new Map<string, Intl.DateTimeFormat>()
export function formatDate(iso: string): string {
  const tag = locale.value === 'uk' ? 'uk-UA' : 'ru-RU'
  let fmt = formatters.get(tag)
  if (!fmt) {
    fmt = new Intl.DateTimeFormat(tag, { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
    formatters.set(tag, fmt)
  }
  return fmt.format(new Date(iso))
}
