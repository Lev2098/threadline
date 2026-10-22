export interface Attachment {
  kind: 'image' | 'text'
  url: string
  name: string
  size: number
  width: number | null
  height: number | null
}

export interface Comment {
  id: number
  parent_id: number | null
  root_id: number
  depth: number
  path: string
  username: string
  email: string
  home_page: string | null
  html: string
  created_at: string
  replies_count: number
  attachment: Attachment | null
}

export interface CommentPage {
  items: Comment[]
  page: number
  pages: number
  page_size: number
  total: number
}

export interface ThreadSlice {
  items: Comment[]
  next_cursor: string | null
}

export interface Captcha {
  key: string
  image: string
  ttl: number
}

export type SortField = 'created_at' | 'username' | 'email'
export type Ordering = SortField | `-${SortField}`

export interface ApiErrorBody {
  code: string
  message: string
  errors: Record<string, string>
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: ApiErrorBody,
  ) {
    super(body.message)
  }
}
